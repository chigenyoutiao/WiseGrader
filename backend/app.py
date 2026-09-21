from openai import OpenAI
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import os
import uuid
import threading
from pathlib import Path
from datetime import datetime
import secrets
import json
import shutil
import subprocess
import sys
import zipfile

from typing import Optional, List, Dict

import config
from utils.zip_handler import process_double_layer_zip
from utils.file_reader import read_file_content
from utils.job_store import REDIS_AVAILABLE, REDIS_HOST, REDIS_PORT, get_job, get_job_key, save_job
from celery_worker import celery_app, update_job_status, grade_job
from utils.file_reader import read_file_content
from utils.doc_parser import evaluate_docx_formatting # <--- 引入这个
from utils.ai_grader import get_ai_grading
from utils.name_parser import parse_student_info

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# 启用CORS（允许前端跨域访问）
CORS(app, supports_credentials=True)

# 存储活跃的token（内存中）
active_tokens = set()

_xxt_runner_lock = threading.Lock()
_xxt_runner_thread: Optional[threading.Thread] = None
agent_sessions: Dict[str, Dict] = {}


def resolve_chat_base_url(model: Optional[str]) -> str:
    """根据模型前缀选择兼容的 Chat API Base URL。"""
    normalized = (model or "").strip().lower()

    print(f"[Model Debug] 当前模型: {normalized}")
    routes = [
        (("gpt-", "o3", "openai"), "https://api.openai.com/v1"),
        (("deepseek",), "https://api.deepseek.com"),
        (("moonshot", "kimi"), "https://api.moonshot.cn/v1"),
        (("glm", "chatglm"), "https://open.bigmodel.cn/api/paas/v4"),
        (("qwen", "wanx"), "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        (("doubao",), "https://ark.cn-beijing.volces.com/api/v3"),
    ]
    for prefixes, base_url in routes:
        if any(prefix in normalized for prefix in prefixes):
            print(f"[Model Debug] 匹配到 Base URL: {base_url}")
            return base_url

    print(f"[Model Debug] 未匹配，使用默认 Kimi 通道")
    return "https://api.moonshot.cn/v1"


def has_active_celery_worker(timeout=1):
    try:
        inspector = celery_app.control.inspect(timeout=timeout)
        if not inspector:
            return False
        stats = inspector.stats()
        return bool(stats)
    except Exception as exc:
        print(f"[Celery] 检测worker失败: {exc}")
        return False


def run_grading_sync(job_id, model, api_key, grading_criteria, feedback_style, grading_targets=None, target_student_ids=None):
    def _runner():
        try:
            print(f"[同步批改] 未检测到Celery worker，改为同步执行: {job_id}")
            grade_job.apply(
                args=[job_id, model, api_key, grading_criteria, feedback_style, grading_targets or {}, target_student_ids or []]
            )
        except Exception as exc:
            print(f"[同步批改] 执行失败: {exc}")

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return thread


def create_job_from_zip(zip_path: Path, job_id: Optional[str] = None, copy_source: bool = True):
    source_path = Path(zip_path)
    if not source_path.exists():
        raise FileNotFoundError(f"ZIP 文件不存在: {source_path}")

    job_id = job_id or f"job_{uuid.uuid4().hex[:8]}"
    destination_zip = config.UPLOAD_FOLDER / f"{job_id}.zip"

    if copy_source or source_path.resolve() != destination_zip.resolve():
        shutil.copy2(source_path, destination_zip)
        working_zip = destination_zip
    else:
        working_zip = source_path

    temp_dir = config.TEMP_FOLDER / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[处理] 开始处理作业包: {job_id}")
    students = process_double_layer_zip(working_zip, temp_dir)

    job_data = {
        "job_id": job_id,
        "status": "uploaded",
        "created_at": datetime.now().isoformat(),
        "students": students,
        "results": [],
        "progress": {"completed": 0, "total": len(students)},
        "source": str(source_path),
    }

    save_job(job_id, job_data)
    storage_backend = "Redis" if REDIS_AVAILABLE else "内存"
    print(f"[存储] 任务已保存到{storage_backend}: {get_job_key(job_id)}")

    return job_id, len(students), job_data


def run_xxt_script(*script_args):
    script_path = config.XXT_SCRIPT_PATH
    if not script_path or not script_path.exists():
        raise FileNotFoundError("学习通脚本未配置或已移除，请设置 XXT_SCRIPT_PATH")

    cmd = [sys.executable, str(script_path), *script_args]
    print(f"[XXT] 运行脚本: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=script_path.parent,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        print(f"[XXT] 脚本输出:\n{result.stdout}\n{result.stderr}")
        raise RuntimeError(f"学习通脚本执行失败: {result.stderr.strip() or result.stdout.strip()}")
    print(f"[XXT] 脚本输出:\n{result.stdout}")
    return result.stdout


def read_xxt_state() -> dict:
    state_file = config.XXT_STATE_FILE
    if not state_file.exists():
        return {}
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as exc:
        print(f"[XXT] 读取状态文件失败: {exc}")
        return {}


def write_xxt_state_snapshot(stage: str, message: Optional[str] = None, **extra):
    payload = {
        "stage": stage,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    try:
        with open(config.XXT_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[XXT] 写入状态文件失败: {exc}")


def _is_xxt_runner_busy() -> bool:
    global _xxt_runner_thread
    thread = _xxt_runner_thread
    return thread is not None and thread.is_alive()


def _start_xxt_runner_async(args: List[str]):
    global _xxt_runner_thread

    def _runner():
        try:
            run_xxt_script(*args)
        except Exception as exc:
            print(f"[XXT] Runner 执行失败: {exc}")
            write_xxt_state_snapshot("error", f"脚本执行失败: {exc}")
        finally:
            global _xxt_runner_thread
            with _xxt_runner_lock:
                _xxt_runner_thread = None

    with _xxt_runner_lock:
        if _is_xxt_runner_busy():
            raise RuntimeError("学习通脚本正在运行中")
        thread = threading.Thread(target=_runner, daemon=True)
        _xxt_runner_thread = thread
        thread.start()


def generate_token():
    return secrets.token_urlsafe(32)


def verify_token(token):
    if token == "dev-permanent-token": 
        return True
    return token in active_tokens


def get_token_from_request():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


def _get_authenticated_token():
    token = get_token_from_request()
    if token and verify_token(token):
        return token
    cookie_token = request.cookies.get('agent_session')
    if cookie_token and verify_token(cookie_token):
        return cookie_token
    return None


def ensure_agent_token():
    token = _get_authenticated_token()
    new_token = None
    if not token:
        token = generate_token()
        active_tokens.add(token)
        new_token = token
        get_or_create_agent_session(token)
        print(f"[Auth] 🙋‍♂️ 新访客接入，自动分配 Token: {token[:8]}...")
    return token, new_token


def make_json_response(payload, new_token: Optional[str] = None):
    resp = make_response(jsonify(payload))
    if new_token:
        secure_cookie = request.is_secure or app.config.get('SESSION_COOKIE_SECURE', False)
        resp.set_cookie(
            'agent_session',
            new_token,
            httponly=True,
            secure=secure_cookie,
            samesite='Lax',
            max_age=7 * 24 * 60 * 60,
        )
    return resp


def get_or_create_agent_session(user_token: str) -> Dict:
    session = agent_sessions.get(user_token)
    if session is None:
        session = {
            "stage": "awaiting_login",
            "course": None,
            "exam": None,
            "criteria": None,
            "feedbackStyle": None,
            "passRate": None,
            "history": [],
            "pending_fill_score": False,  # 🟢 新增：标记是否有待处理的回填请求
            "last_job_id": None,
        }
        agent_sessions[user_token] = session
    return session


def build_agent_response(message: str, session: Dict, options=None, next_action=None):
    response = {
        "success": True,
        "stage": session.get("stage"),
        "message": message,
        "session": {
            "course": session.get("course"),
            "exam": session.get("exam"),
            "criteria": session.get("criteria"),
            "feedbackStyle": session.get("feedbackStyle"),
            "passRate": session.get("passRate"),
        },
    }
    if options:
        response["options"] = options
    if next_action:
        response["nextAction"] = next_action
    return response


def handle_parameter_message(text: str, session: Dict):
    updated = False
    if "标准" in text:
        session["criteria"] = text
        updated = True
    if "评语" in text or "风格" in text:
        session["feedbackStyle"] = text
        updated = True
    return updated


# =================================================
# AI 意图分析函数 (带记忆 + 成绩单感知)
# =================================================
# app.py



def analyze_intent_with_ai(user_message, model, api_key, user_lang="zh", history=[], job_context=None, has_uploaded_file=False, current_chat_files=[], file_content_str=None, pending_fill_score=False):
    client = OpenAI(
        api_key=api_key,
        base_url=resolve_chat_base_url(model),
    )

    # 1. 构建上下文数据 (Context Data)
    context_data = ""
    has_history_doc = False 

    # (A) 检查历史文档
    if history:
        for msg in history:
            content = str(msg.get("content", ""))
            if "【系统记忆：用户上传了文档】" in content:
                has_history_doc = True
                break
    if has_history_doc:
        context_data += "\n[历史记忆] 包含用户之前上传的文档内容。\n"

    # (B) 检查当前文档内容
    if file_content_str:
        context_data += f"\n[当前上传文档内容] (摘要):\n{file_content_str[:500]}...\n(完整内容已接收)\n"
        if "【用户配置的评分标准】" in file_content_str:
             context_data += "[检测到评分标准] 用户配置了具体评分标准。\n"

    # (C) 检查当前文件列表
    if current_chat_files:
        files_str = ", ".join(current_chat_files)
        context_data += f"\n[当前附件] {files_str}\n"

    # (D) 检查之前的 ZIP 任务
    if has_uploaded_file:
        context_data += f"\n[后台状态] 存在已上传的 ZIP 作业包。\n"

    # (E) 注入成绩单上下文 (关键点！)
    if job_context:
        context_data += f"\n[当前任务成绩单数据]\n{job_context}\n"
    
    # (F) 🟢 新增：注入待回填状态
    if pending_fill_score:
        context_data += f"\n[重要上下文] 用户刚才请求了\"回填分数\"，但缺少课程和考试信息。现在用户回复的消息可能是提供课程和考试名称，用于完成回填操作。请优先识别为 fill_score 意图。\n"

    # 2. 构建 System Prompt (指令置后策略)
    # 根据语言选择基础指令
    lang_instruction = "请用中文回答。" if user_lang != "en" else "Answer in English."
    
    system_prompt = f"""
    你是 WiseGrader 智能助手的“意图识别引擎”。
    你不是聊天机器人，你是一个逻辑分析器。
    
    【你的任务】
    分析用户的输入 (`user_message`) 和提供的上下文 (`context_data`)，输出一个 JSON 指令。

    【判断规则】
    1. **grading (单篇批改)**: 
       - 条件：用户上传了新文档(PDF/DOCX)，且意图是"批改/评分/看看作业"。
       - 优先级：最高。
    2. **grading (批量/自动)**: 
       - 条件：用户上传了 ZIP。
       - 或者：用户明确指定了【课程名称】和【作业/考试名称】（例如："批改区块链课的期末考"），且**不是**回填操作。
       - **重要**: 如果用户指定了课程，reply 中请回答 "收到，准备连接学习通获取 [课程名] 的 [作业名]..."，**千万不要**让用户上传文件。
    3. **export (导出)**: 
       - 条件：用户想下载/导出 Excel/表格。
    4. **fill_score (回填分数)**:
       - 条件：用户明确表示要"回填"、"填分"、"上传成绩"、"同步到学习通"、"把分数填回去"。
       - **关键判断1**：如果上下文中有 [重要上下文] 标记（表示有待处理的回填请求），且用户回复的是课程和考试名称，**必须**识别为 fill_score。
       - **关键判断2**：如果用户说"回填分数"、"回填"、"填分"等，且上下文中有批改结果（job_context 不为空），优先识别为 fill_score。
       - 如果用户同时提到课程和考试名称（如"回填智能合约的期末考试"），请提取 course 和 exam 字段。
       - 例如："回填分数"、"把分数填回去"、"回填一下"、"同步成绩到学习通"、"回填智能合约的期末考试"。
    5. **chat (问答模式)**: 
       - 条件：
         - 用户询问关于 [当前任务成绩单数据] 的问题 (如"谁最高分?", "平均分多少?")。
         - 用户询问关于文档内容的问题 (如"写了什么?")。
         - 普通闲聊。
       - **重要**: 在 `reply` 字段中，根据上下文数据直接回答用户的问题。不要说"我去查一下"，直接利用已有数据回答。

    【上下文数据】
    {context_data}

    【输出格式要求 - 严禁违反】
    1. 必须且只能返回 **纯 JSON 字符串**。
    2. 不要包含 ```json 或 ``` 标记。
    3. JSON 结构:
    {{
        "intent": "grading" | "chat" | "export" | "fill_score",
        "course": "...", 
        "exam": "...", 
        "reply": "在这里直接写出回复内容（如果是 chat 模式，请根据上下文数据生成最终回答）"
    }}
    
    {lang_instruction}
    """

    # 3. 构建消息链
    # 注意：这里我们不把冗长的 history 全部塞给 LLM 用于意图判断，
    # 只保留最近 2 条，避免干扰 JSON 输出，同时节省 Token。
    # 意图判断主要靠 system_prompt 里的 context_data。
    recent_history = history[-2:] if history else [] 
    formatted_history = []
    for msg in recent_history:
        if msg.get("role") and msg.get("content"):
            formatted_history.append({
                "role": msg["role"], 
                # 截断历史消息内容，防止 Prompt 过长
                "content": str(msg["content"])[:200] 
            })

    messages = [
        {"role": "system", "content": system_prompt},
        *formatted_history, 
        {"role": "user", "content": user_message}
    ]

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1, # 极低温度，保证格式稳定
            response_format={ "type": "json_object" } # 🟢 启用 JSON 模式 (如果模型支持)
        )
        content = completion.choices[0].message.content.strip()
        
        # 再次清理，双重保险
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()
            
        return json.loads(content)

    except Exception as e:
        print(f"[AI Intent Error] 解析失败: {e}")
        # 降级处理：如果解析失败，默认当作普通聊天，避免 500 错误
        return {
            "intent": "chat",
            "reply": "抱歉，我正在处理大量数据，稍微有点卡顿。您能再说一遍您的问题吗？"
        }
# ===========================
# API 路由
# ===========================

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')

    if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        token = "dev-permanent-token"
        active_tokens.add(token)
        return make_json_response({
            "success": True,
            "token": token,
            "message": "登录成功"
        }, new_token=token)
    else:
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401


@app.route('/api/upload/jobs', methods=['POST'])
def upload_jobs():
    token, new_token = ensure_agent_token()
    if 'file' not in request.files:
        return make_json_response({"success": False, "error": "未找到文件"}, new_token=new_token), 400

    file = request.files['file']
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    upload_path = config.UPLOAD_FOLDER / f"{job_id}.zip"
    file.save(upload_path)

    try:
        job_id, student_count, _ = create_job_from_zip(upload_path, job_id=job_id, copy_source=False)
        return make_json_response({
            "success": True,
            "jobId": job_id,
            "studentCount": student_count
        }, new_token=new_token)
    except Exception as e:
        return make_json_response({"success": False, "error": str(e)}, new_token=new_token), 500


@app.route('/api/agent', methods=['POST'])
def agent_endpoint():
    """AI 全权托管模式：自动识别意图"""
    token, new_token = ensure_agent_token()

    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    user_lang = payload.get("language", "zh") 

    # =================================================
    # 获取会话和配置
    # =================================================
    session = get_or_create_agent_session(token)
    
    # 1. 获取并更新 API Key
    incoming_api_key = payload.get("apiKey") or payload.get("apikey")
    if incoming_api_key:
        session["apiKey"] = incoming_api_key.strip()
    api_key = session.get("apiKey")
    
    # 2. 获取并更新 Model
    incoming_model = (payload.get("model") or "").strip()
    if incoming_model:
        session["model"] = incoming_model
    model = session.get("model") or "moonshot-v1-8k"

    # 3. 获取 Context (文件ID / 任务ID)
    context = payload.get("context") or {}
    uploaded_job_id = context.get("uploadedJobId")
    current_job_id = context.get("currentJobId")
    last_job_id = context.get("lastJobId")
    pending_fill_score_hint = context.get("pendingFillScore")
    # 🟢 新增：获取当前聊天附带的文件名
    current_chat_files = context.get("currentChatFiles") or []
    # 🟢 【修改点】计算是否有文件
    has_uploaded_file = bool(uploaded_job_id)
    # 获取 fileContent
    file_content = context.get("fileContent")
    # 🟢 同步 criteria
    incoming_criteria = payload.get("criteria")
    if incoming_criteria:
        session["criteria"] = incoming_criteria
    if last_job_id and not current_job_id:
        if get_job(last_job_id):
            session["last_job_id"] = last_job_id
    if pending_fill_score_hint:
        session["pending_fill_score"] = True
    # =========================================================
    # 🟢 1. 智能识别：如果是纯文本且包含“标准”，自动更新 session
    # =========================================================
    # 如果用户说 "评分标准是：xxxx"，我们自动把它存起来
    if "标准" in message or "criteria" in message.lower():
        # 简单粗暴：认为用户这一整句就是新标准
        # 或者你可以做更复杂的提取，但通常直接覆盖就行
        session["criteria"] = message
        print(f"[设置] 从对话中更新了评分标准: {message[:20]}...")

    # =========================================================
    # 🟢 2. 核心修复：文件暂存机制 (Cache)
    # =========================================================
    # 如果这次传了新文件，把它存进 session，覆盖旧的
    if file_content:
        # 解析一下名字备用
        filename = current_chat_files[0] if current_chat_files else "未知学生.docx"
        student_info = parse_student_info(filename)
        
        session["cached_single_file"] = {
            "content": file_content,
            "filename": filename,
            "s_name": student_info['student_name'],
            "s_id": student_info['student_id']
        }
        print("[Cache] 已暂存单文件内容，等待指令...")

    # 定义响应辅助函数
    def respond(text, **kwargs):
        return make_json_response(build_agent_response(text, session, **kwargs), new_token=new_token)

    if not message and not file_content:
        return respond("请告诉我需要批改的课程和考试。")

    if not api_key:
        return respond("请先在右侧配置面板设置 API Key，我才能开始工作。")

    # =================================================
    # 准备上下文 (History + Job Data)
    # =================================================
    history = session.get("history", [])

    if file_content:
        print(f"[Agent] 收到新文档内容，正在写入记忆... (长度: {len(file_content)})")
        # 把文件内容伪装成一条系统提示，塞进历史记录
        # 这样无论下一轮对话用户问什么，AI 都能往上翻到这条记录
       # 为了不让历史记录太乱，我们可以加个标记
        memory_message = {
            "role": "system", 
            "content": f"【系统记忆：用户上传了文档】\n{file_content}\n\n(注意：这是用户刚才上传的文档内容。在接下来的对话中，如果用户询问'这个文档'或'格式问题'，请直接基于上述内容回答，不要说你不知道。)"
        }
        history.append(memory_message)
        # 存回 session
        session["history"] = history
    
  
    # =================================================
    # 🌟 完美版：智能动态上下文构建 (Intelligent Context Builder)
    # =================================================
    job_context_str = None
    if current_job_id:
        session["last_job_id"] = current_job_id
        job = get_job(current_job_id)
        # 确保有结果且 message 不为空
        if job and job.get('results') and message:
            results = job.get('results', [])
            
            # 1. 🔍 侦探模式：检查用户是否提到了具体的学生名字
            # (这解决了"第31个学生"的问题，因为我们在全量搜索)
            target_student = None
            for r in results:
                s_name = r.get('studentName', '')
                if s_name and s_name in message:  # 简单的包含匹配
                    target_student = r
                    break
            
            # 2. 📝 构建上下文：根据是否找到目标，提供不同精度的信息
            if target_student:
                # 【场景 A：用户问特定学生】-> 提供 100% 详细的完整信息
                # 提取格式问题详情
                fmt_checks = target_student.get('formattingChecks', [])
                failed_issues = [f['message'] for f in fmt_checks if not f['passed']]
                fmt_summary = "; ".join(failed_issues) if failed_issues else "格式规范，无扣分项"
                
                job_context_str = f"""
                【🎯 重点关注对象数据】
                用户提到的学生：{target_student.get('studentName')}
                ----------------------------------
                - 总分：{target_student.get('score')} 分
                - 内容得分：{target_student.get('contentScore')} | 格式得分：{target_student.get('formattingScore')}
                - 格式情况：{fmt_summary}
                - 完整评语(无截断)：{target_student.get('feedback')}
                ----------------------------------
                (请基于以上完整信息详细回答用户关于该学生的问题)
                """
                print(f"[Context] 🎯 命中学生：{target_student.get('studentName')}")
                
            else:
                # 【场景 B：用户没提名字/问整体】-> 提供班级统计 + 简略名单
                # 计算统计数据 (AI 喜欢数据！)
                total_students = len(results)
                scores = [r.get('score', 0) or 0 for r in results]
                avg_score = sum(scores) / total_students if total_students > 0 else 0
                max_score = max(scores) if scores else 0
                min_score = min(scores) if scores else 0
                failed_count = len([s for s in scores if s < 60])
                
                # 生成简略名单 (只包含名字和分数，节省 Token)
                # 即使是简略名单，我们放宽到前 50-60 人也没问题，因为去掉了长评语
                simple_list = []
                for r in results[:60]: 
                    simple_list.append(f"{r.get('studentName')}:{r.get('score')}分")
                
                list_str = ", ".join(simple_list)
                if len(results) > 60: list_str += "..."

                job_context_str = f"""
                【📊 班级整体统计数据】
                - 作业总份数：{total_students}
                - 平均分：{avg_score:.1f} (最高：{max_score} / 最低：{min_score})
                - 不及格人数：{failed_count}
                
                【学生分数速查表】
                {list_str}
                
                (用户未指定具体姓名。如果用户询问某位具体学生的详细评语，请引导用户提供学生姓名，你再进行详细查询。)
                """
                print(f"[Context] 📊 生成班级统计概览")
    
    # 🟢 调用 AI (传入所有上下文)
    # 🟢 检查是否有待处理的回填请求
    pending_fill_score = session.get("pending_fill_score", False)
    ai_decision = analyze_intent_with_ai(
        message, 
        model,
        api_key,
        user_lang, 
        history, 
        job_context=job_context_str,
        has_uploaded_file=bool(uploaded_job_id),
        current_chat_files=current_chat_files,
        file_content_str=file_content,
        pending_fill_score=pending_fill_score  # 🟢 传入待回填状态
        )
    
    intent = ai_decision.get("intent", "chat")
    reply_text = ai_decision.get("reply", "我没听懂...")
    fill_keywords = ("回填", "填分", "同步成绩", "同步分数", "上传成绩", "把分数填回去", "回填分数")
    if pending_fill_score or any(k in message for k in fill_keywords):
        intent = "fill_score"

    # 🟢 更新历史记录 (User)
    session.setdefault("history", []).append({"role": "user", "content": message})

    if intent == "grading":
      # =========================================================
        # 🟢 场景 A：单文件严格批改 (支持暂存文件)
        # =========================================================
        # 优先使用当前文件，如果没有，使用暂存文件
        target_file = None
        if file_content:
            target_file = session["cached_single_file"] # 刚才已经存进去了
        elif session.get("cached_single_file"):
            target_file = session["cached_single_file"]
            print("[Agent] 使用暂存的文件进行重批...")

        # 只要找到了目标文件（无论是刚传的还是暂存的），就批改
        if target_file:
            # 1. 获取标准
            criteria_text = session.get("criteria")
            if not criteria_text or len(criteria_text) < 5:
                criteria_text = "（用户未配置具体标准，请基于：内容完整性40%，逻辑清晰度30%，格式规范30% 进行严格打分）"

            # 2. 准备数据
            s_name = target_file['s_name']
            s_id = target_file['s_id']
            content_to_grade = target_file['content']

            # 3. Prompt (保持不变)
            grading_prompt = f"""
            你是一位极其严格、反对"平均分"和"惰性评分"的大学教授。
            现在需要你批改一份单独提交的作业。请完全依据下方的【评分标准】进行量化打分。

            【学生信息】
            姓名：{s_name}
            学号：{s_id}

            【评分标准】 (必须严格执行!)
            {criteria_text}

            【作业内容】
            {content_to_grade}

            【输出指令】
            请忽略之前的聊天上下文，直接进入"阅卷模式"。
            请严格按照以下格式输出 Markdown 文本（不要输出 JSON，直接输出可读文本）：

            ### 1. 基本信息
            - **姓名**：{s_name}
            - **学号**：{s_id}

            ### 2. 最终得分
            **[这里填分数] 分** *(评分依据：请简要说明扣分点)*

            ### 3. 详细批语
            [请根据评分标准，指出具体的优点和不足...]

            ### 4. 格式检查
            [基于文档内容检查排版、标题、段落等...]

            ### 5. 教师教学建议
            [根据作业反映出的共性或特性问题，给老师的教学建议...]

            ### 6. 学生未来改进
            [给该学生的具体学习提升路径...]
            """

            try:
                print(f"[Agent] 执行批改... (模型: {model})")
                client = OpenAI(api_key=api_key, base_url=resolve_chat_base_url(model))
                completion = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": grading_prompt}],
                    temperature=0.2
                )
                final_reply = completion.choices[0].message.content
                session["history"].append({"role": "assistant", "content": final_reply})
                return respond(final_reply)
            except Exception as e:
                return respond(f"批改出错: {e}")

        # ---------------------------------------------------------
        # 🟢 场景 B：ZIP 批量批改 (原有逻辑)
        # ---------------------------------------------------------
        elif uploaded_job_id:
            print(f"[Agent] 检测到本地 ZIP 文件 {uploaded_job_id}，准备批量批改。")
            action = {
                "type": "start_runner",
                "course": "本地文件",
                "exam": "上传的作业",
                "sidebar": "上传",
                "skipDownload": True, 
                "jobId": uploaded_job_id 
            }
            final_reply = f"✅ 已识别 ZIP 包，准备开始批量批改..."
            session["history"].append({"role": "assistant", "content": final_reply})
            return respond(final_reply, next_action=action)
            
        # ---------------------------------------------------------
        # 🟢 场景 C：学习通自动化 (原有逻辑)
        # ---------------------------------------------------------
        else:
            course_name = ai_decision.get("course")
            exam_name = ai_decision.get("exam")
            sidebar = ai_decision.get("sidebar") or "考试"

            if course_name and exam_name:
                session["course"] = course_name
                session["exam"] = exam_name
                action = {
                    "type": "start_runner",
                    "course": course_name,
                    "exam": exam_name,
                    "sidebar": sidebar,
                }
                final_reply = f"✅ 已识别课程：**{course_name}** - **{exam_name}**。\n即将启动学习通自动下载与批改流程..."
                session["history"].append({"role": "assistant", "content": final_reply})
                return respond(final_reply, next_action=action)
            else:
                error_reply = "我好像知道你想批改作业，但没听清是哪门课（或者请先上传 ZIP/文档）。"
                session["history"].append({"role": "assistant", "content": error_reply})
                return respond(error_reply)
    # 🟢 新增：处理回填分数逻辑
    elif intent == "fill_score":
        # 1. 检查是否有任务上下文（优先使用当前任务，其次使用最近任务）
        job_id = current_job_id or session.get("last_job_id")
        if not job_id:
            session["pending_fill_score"] = True
            error_reply = "抱歉，我找不到当前批改任务记录。请先完成批改，或从历史记录中选择最近的批改任务。"
            session["history"].append({"role": "assistant", "content": error_reply})
            return respond(error_reply)
        
        # 2. 检查必要信息
        # 优先从 AI 识别的结果拿，如果没有，就从会话缓存(session)里拿
        target_course = ai_decision.get("course") or session.get("course")
        target_exam = ai_decision.get("exam") or session.get("exam")
        
        # 🟢 如果 AI 从消息中提取到了课程和考试，保存到 session
        if ai_decision.get("course") and ai_decision.get("exam"):
            session["course"] = ai_decision.get("course")
            session["exam"] = ai_decision.get("exam")
            target_course = session["course"]
            target_exam = session["exam"]
            print(f"[回填] 从消息中提取到课程信息: {target_course} - {target_exam}")
        
        # 3. 检查课程信息是否完整
        if not target_course or not target_exam:
            # 🟢 标记待回填状态，这样下次用户回复课程信息时，AI 会优先识别为 fill_score
            session["pending_fill_score"] = True
            # 如果 AI 没提取到，session 里也没有，就反问用户
            ask_reply = "好的，但我需要确认一下：这是哪门课程的哪个考试？（请回复如：‘智能合约的期末考试’）"
            session["history"].append({"role": "assistant", "content": ask_reply})
            return respond(ask_reply)

        # 4. 一切就绪，触发脚本！
        # 这里复用我们之前写的启动逻辑
        try:
            # 准备数据文件
            config.TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
            scores_file = config.TEMP_FOLDER / f"scores_{job_id}.json"
            
            # 从 Redis 获取 Job 数据
            job = get_job(job_id)
            if not job: raise Exception("任务数据丢失")
            
            # 生成简单的分数 JSON
            scores_map = {}
            for res in job.get('results', []):
                if res.get('studentId') and res.get('score') is not None:
                    scores_map[res['studentId']] = {
                        "score": res['score'],
                        "feedback": res.get('feedback', '')
                    }
            
            with open(scores_file, 'w', encoding='utf-8') as f:
                json.dump(scores_map, f, ensure_ascii=False)
            
            # 启动子进程
            backend_dir = Path(__file__).parent.resolve()
            script_path = backend_dir / "xxt" / "grader.py"
            
            cmd = [
                sys.executable, str(script_path),
                "--course", target_course,
                "--exam", target_exam,
                "--scores-file", str(scores_file)
            ]
            
            print(f"[回填] 启动命令: {' '.join(cmd)}")
            subprocess.Popen(cmd, cwd=str(backend_dir))
            
            # 5. 回复用户
            final_reply = f"✅ 回填任务已启动！正在将 {len(scores_map)} 名学生的成绩同步至学习通《{target_course}》的《{target_exam}》...\n\n请查看浏览器窗口，完成登录和回填操作。"
            session["history"].append({"role": "assistant", "content": final_reply})
            # 🟢 确保保存课程和考试信息到 session，供后续使用
            session["course"] = target_course
            session["exam"] = target_exam
            # 🟢 清除待回填状态
            session["pending_fill_score"] = False
            return respond(final_reply)
            
        except Exception as e:
            err_msg = f"启动回填失败: {str(e)}"
            session["history"].append({"role": "assistant", "content": err_msg})
            return respond(err_msg)
    # 🟢 新增：处理导出逻辑
    elif intent == "export":
        # 如果当前有正在聊的任务 ID
        if current_job_id:
            action = {
                "type": "trigger_export",  # 这是一个自定义的动作类型
                "jobId": current_job_id
            }
            # AI 的回复
            final_reply = "好的，正在为您生成 Excel 成绩单，请稍候..."
            session["history"].append({"role": "assistant", "content": final_reply})
            return respond(final_reply, next_action=action)
        else:
            # 如果没有任务 ID，尴尬了
            error_reply = "抱歉，我找不到刚才批改的任务记录，无法生成表格。"
            session["history"].append({"role": "assistant", "content": error_reply})
            return respond(error_reply)
    else:
        # 🟢 更新历史记录 (Assistant - Chat)
        session["history"].append({"role": "assistant", "content": reply_text})
        return respond(reply_text)


@app.route('/api/xxt/state', methods=['GET'])
def get_xxt_state():
    token, new_token = ensure_agent_token()
    state = read_xxt_state()
    return make_json_response({"success": True, "state": state}, new_token=new_token)


@app.route('/api/xxt/start', methods=['POST'])
def start_xxt_runner():
    token, new_token = ensure_agent_token()
    if not config.XXT_SCRIPT_PATH or not config.XXT_SCRIPT_PATH.exists():
        return make_json_response({"success": False, "error": "学习通脚本未配置或已移除，请设置 XXT_SCRIPT_PATH"}, new_token=new_token), 400
    if _is_xxt_runner_busy():
        return make_json_response({"success": False, "error": "脚本运行中"}, new_token=new_token), 409

    payload = request.get_json(silent=True) or {}
    mode = payload.get('mode', 'download')
    course = payload.get('course')
    exam = payload.get('exam')
    sidebar = payload.get('sidebar')
    class_list = payload.get('classes')  # 可选：指定班级列表
    backend_url = payload.get('backendUrl') or request.url_root.rstrip('/')

    script_args = ['--course', course, '--exam', exam, '--sidebar', sidebar, '--backend-url', backend_url]
    if class_list:
        if isinstance(class_list, list):
            classes_arg = ",".join(class_list)
        else:
            classes_arg = str(class_list)
        script_args.extend(['--classes', classes_arg])
    script_token = generate_token()
    active_tokens.add(script_token)
    script_args.extend(['--backend-token', script_token])

    write_xxt_state_snapshot("queued", f"即将执行", course=course, exam=exam)
    try:
        _start_xxt_runner_async(script_args)
    except RuntimeError as exc:
        return make_json_response({"success": False, "error": str(exc)}, new_token=new_token), 409

    return make_json_response({"success": True}, new_token=new_token)


@app.route('/api/upload/criteria-file', methods=['POST'])
def upload_criteria_file():
    token, new_token = ensure_agent_token()
    if 'file' not in request.files:
        return make_json_response({"success": False, "error": "未找到文件"}, new_token=new_token), 400

    file = request.files['file']
    filename = file.filename or ""
    if not filename:
        return make_json_response({"success": False, "error": "文件名为空"}, new_token=new_token), 400

    ext = Path(filename).suffix.lower()
    if not ext: ext = ".txt"

    file_id = uuid.uuid4().hex[:8]
    upload_path = config.UPLOAD_FOLDER / f"criteria_{file_id}{ext}"
    
    try:
        file.seek(0)
        file.save(upload_path)
        
        if not upload_path.exists() or upload_path.stat().st_size == 0:
             return make_json_response({"success": False, "error": "保存的文件为空"}, new_token=new_token), 400

        criteria_text = read_file_content(upload_path)
        if not criteria_text:
             return make_json_response({"success": False, "error": "无法识别文件内容"}, new_token=new_token), 400

        return make_json_response({"success": True, "criteriaText": criteria_text}, new_token=new_token)

    except Exception as e:
        print(f"[上传失败] {e}")
        return make_json_response({"success": False, "error": str(e)}, new_token=new_token), 500


@app.route('/api/upload/chat-file', methods=['POST'])
def upload_chat_file():
    """
    专门用于聊天时上传单个文档（PDF/DOCX），提取文本+格式报告
    """
    token, new_token = ensure_agent_token()
    if 'file' not in request.files:
        return make_json_response({"success": False, "error": "未找到文件"}, new_token=new_token), 400

    file = request.files['file']
    # 🟢 获取前端传来的 criteria (Form Data)
    incoming_criteria = request.form.get('criteria', '').strip()
    
    # 如果有新标准，更新 Session
    session = get_or_create_agent_session(token)
    if incoming_criteria:
        session['criteria'] = incoming_criteria
    filename = file.filename or "unknown"
    
    # 保存临时文件
    temp_id = uuid.uuid4().hex[:8]
    ext = Path(filename).suffix.lower()
    save_path = config.TEMP_FOLDER / f"chat_{temp_id}{ext}"
    config.TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
    
    try:
        file.save(save_path)
        
        # 1. 基础提取：读取文本内容
        content = read_file_content(save_path)
        # 2. 进阶分析：生成“客观参数表”
        doc_stats_str = ""
        if ext == '.docx':
            try:
                fmt_result = evaluate_docx_formatting(str(save_path))
                metrics = fmt_result.get('metrics', {})
                
                # 🟢 生成纯客观的测量报告
                doc_stats_str = f"""
【文档格式测量数据】(供 AI 裁判参考)
- 标题层级: {metrics.get('heading_levels')}
- 正文主流字号: {metrics.get('dominant_font_size')}
- 正文主流行距: {metrics.get('dominant_spacing')}
- 正文首行缩进: {metrics.get('dominant_indent')}
- 页眉页脚状态: {metrics.get('header_footer_status')} ({metrics.get('header_footer_detail')})
- 统计数据: {metrics.get('paragraph_count')}段落, {metrics.get('figure_count')}图片, {metrics.get('table_count')}表格
"""
                # 优先使用带格式的 markdown
                if fmt_result.get('markdown'):
                    content = fmt_result['markdown']

            except Exception as e:
                print(f"[格式分析失败] {e}")

        # 3. 注入评分标准
        criteria_text = incoming_criteria or session.get("criteria", "")

        # 4. 拼装最终内容
        # 顺序：文档正文 -> 格式测量数据 -> 评分标准
        final_text = f"【文档正文内容】\n{content}\n\n"
        
        if doc_stats_str:
            final_text += f"{doc_stats_str}\n"
            
        if criteria_text:
            final_text += f"【用户配置的评分标准】\n{criteria_text}\n(请严格依据此标准进行评分。对于标准中未提及的格式要求，请忽略测量数据中的相关项。)\n"

        return make_json_response({
            "success": True, 
            "text": final_text, 
            "filename": filename or "unknown"
        }, new_token=new_token)
    except Exception as e:
        print(f"[文件读取失败] {e}")
        return make_json_response({"success": False, "error": str(e)}, new_token=new_token), 500



@app.route('/api/criteria/extract', methods=['POST'])
def extract_criteria():
    token, new_token = ensure_agent_token()
    return make_json_response({"success": True, "extractedPoints": "Mock Points"}, new_token=new_token)


@app.route('/api/jobs/start', methods=['POST'])
def start_grading():
    """开始批改 - 游客通行版"""
    token, new_token = ensure_agent_token()
    data = request.get_json()
    job_id = data.get('jobId')
    model = data.get('model')
    api_key = data.get('apiKey')
    grading_criteria = data.get('gradingCriteria')

    # 🟢 新增：给批量任务也加上兜底
    if not grading_criteria or len(grading_criteria.strip()) < 5:
        grading_criteria = "通用评分标准：内容完整性40%，逻辑清晰度30%，格式规范30%。请严格打分。"
        print(f"[警告] 任务 {job_id} 未配置评分标准，已应用默认通用标准。")
    
    job = get_job(job_id)
    if not job:
        return make_json_response({"success": False, "error": "任务不存在"}, new_token=new_token), 404

    student_total = len(job['students'])
    update_job_status(job_id, status="processing", progress={"completed": 0, "total": student_total})

    if has_active_celery_worker():
        task = celery_app.send_task('tasks.grade_job', args=[job_id, model, api_key, grading_criteria, "", {}, []])
        return make_json_response({"success": True, "taskId": task.id, "mode": "celery"}, new_token=new_token)
    else:
        run_grading_sync(job_id, model, api_key, grading_criteria, "", {}, [])
        return make_json_response({"success": True, "mode": "sync"}, new_token=new_token)


@app.route('/api/jobs/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    token, new_token = ensure_agent_token()
    job = get_job(job_id)
    if not job:
        return make_json_response({"success": False, "error": "任务不存在"}, new_token=new_token), 404
    return make_json_response({
        "success": True,
        "status": job['status'],
        "progress": job['progress'],
        "results": job['results']
    }, new_token=new_token)


@app.route('/api/jobs/export/<job_id>', methods=['GET'])
def export_excel(job_id):
    """
    导出Excel成绩单（完整功能版）
    """
    token, new_token = ensure_agent_token()
    job = get_job(job_id)
    if not job:
        return make_json_response({"success": False, "error": "任务不存在"}, new_token=new_token), 404

    try:
        import pandas as pd
        data = []
        results = job.get('results', [])
        
        if not results:
             return make_json_response({"success": False, "error": "尚无批改结果可导出"}, new_token=new_token), 400

        for result in results:
            formatting_checks = result.get('formattingChecks') or []
            failed_issues = [check.get('message') for check in formatting_checks if not check.get('passed')]
            formatting_issue_summary = "; ".join(failed_issues[:3])
            
            data.append({
                "学号": result.get('studentId', ''),
                "姓名": result.get('studentName', ''),
                "总分": result.get('score') if result.get('score') is not None else "批改失败",
                "内容分": result.get('contentScore', ''),
                "格式分": result.get('formattingScore', ''),
                "格式问题摘要": formatting_issue_summary,
                "AI评语": result.get('feedback', '')
            })

        df = pd.DataFrame(data)
        filename = f"成绩单_{job_id}.xlsx"
        export_path = config.TEMP_FOLDER / filename
        config.TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
        df.to_excel(export_path, index=False, engine='openpyxl')

        response = make_response(send_file(
            export_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
        
        if new_token:
            secure_cookie = request.is_secure or app.config.get('SESSION_COOKIE_SECURE', False)
            response.set_cookie(
                'agent_session',
                new_token,
                httponly=True,
                secure=secure_cookie,
                samesite='Lax',
                max_age=7 * 24 * 60 * 60,
            )
        return response

    except ImportError:
        return make_json_response({"success": False, "error": "服务器缺少导出组件 (pandas/openpyxl)"}, new_token=new_token), 500
        
    except Exception as e:
        print(f"[错误] Excel导出失败: {e}")
        return make_json_response({"success": False, "error": f"导出失败: {str(e)}"}, new_token=new_token), 500
# [app.py] 添加图片访问接口

# [app.py] 确保路径解析准确 - 使用配置中的路径
@app.route('/api/xxt/image/<path:filename>', methods=['GET'])
def get_xxt_image(filename):
    # 🟢 修复：使用配置中的状态文件目录，而不是硬编码路径
    # 图片保存在状态文件同目录下
    image_folder = config.XXT_STATE_FILE.parent
    file_path = image_folder / filename

    print(f"----------------------------------------")
    print(f"[调试] 前端请求图片: {filename}")
    print(f"[调试] 后端锁定目录: {image_folder}")
    print(f"[调试] 最终完整路径: {file_path}")
    print(f"[调试] 文件是否存在: {file_path.exists()}")
    print(f"----------------------------------------")

    if file_path.exists():
        # 返回图片
        return send_file(file_path, mimetype='image/png')
    else:
        print(f"❌ 找不到文件！路径: {file_path}")
        # 🟢 列出目录内容以便调试
        if image_folder.exists():
            print(f"[调试] 目录存在，内容: {list(image_folder.glob('*'))}")
        else:
            print(f"[调试] 目录不存在: {image_folder}")
        return jsonify({"error": "Image not found", "path": str(file_path)}), 404
    #回填分数接口
# [app.py] 新增接口
@app.route('/api/xxt/fill_scores', methods=['POST'])
def start_fill_scores():
    """
    启动自动回填分数脚本
    流程：读取任务结果 -> 转换格式 -> 存为临时文件 -> 启动子进程
    """
    token, new_token = ensure_agent_token()
    data = request.get_json() or {}
    
    job_id = data.get('jobId')
    course_name = data.get('course')
    exam_name = data.get('exam')
    class_name = data.get('className')  # 🟢 新增：接收班级名称

    # 1. 基础校验
    if not all([job_id, course_name, exam_name]):
        return make_json_response({"success": False, "error": "参数不完整 (缺 jobId/course/exam)"}, new_token=new_token), 400

    # 2. 从 Redis/内存 获取任务数据
    job = get_job(job_id)
    if not job:
        return make_json_response({"success": False, "error": "任务不存在"}, new_token=new_token), 404
    
    results = job.get('results', [])
    if not results:
        return make_json_response({"success": False, "error": "该任务没有批改结果，无法回填"}, new_token=new_token), 400

    try:
        # 3. 数据转换 (关键步骤)
        # 将复杂的 Job 结果转换为 grader.py 需要的简单字典格式
        # 🟢 修改：包含学生姓名，用于进度显示
        # 目标格式: { "学号": {"score": 90, "feedback": "...", "studentName": "张三"} }
        scores_map = {}
        student_info_map = {}  # 🟢 新增：学号到学生信息的映射
        for res in results:
            s_id = res.get('studentId') or res.get('student_id')
            s_name = res.get('studentName') or res.get('student_name')
            # 过滤掉没有学号或没有分数的记录
            if s_id and res.get('score') is not None:
                scores_map[s_id] = {
                    "score": res.get('score'),
                    "feedback": res.get('feedback', '')
                }
                # 🟢 保存学生信息映射（用于进度显示）
                if s_name:
                    student_info_map[s_id] = s_name
        
        print(f"[回填] 准备回填 {len(scores_map)} 条数据 (任务ID: {job_id})")

        if not scores_map:
             return make_json_response({"success": False, "error": "有效分数数据为空"}, new_token=new_token), 400

        # 4. 保存为临时 JSON 文件
        # 确保 temp 目录存在
        config.TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
        scores_file_path = config.TEMP_FOLDER / f"scores_{job_id}.json"
        student_info_path = config.TEMP_FOLDER / f"student_info_{job_id}.json"  # 🟢 新增：学生信息文件
        
        with open(scores_file_path, 'w', encoding='utf-8') as f:
            json.dump(scores_map, f, ensure_ascii=False, indent=2)
        
        # 🟢 新增：保存学生信息映射文件（用于进度显示）
        if student_info_map:
            with open(student_info_path, 'w', encoding='utf-8') as f:
                json.dump(student_info_map, f, ensure_ascii=False, indent=2)

        # 5. 启动子进程 (grader.py)
        # 获取 backend 的绝对路径，防止 cwd 报错
        backend_dir = Path(__file__).parent.resolve()
        script_path = backend_dir / "xxt" / "grader.py" # backend/xxt/grader.py

        if not script_path.exists():
             return make_json_response({"success": False, "error": f"找不到脚本文件: {script_path}"}, new_token=new_token), 500

        cmd = [
            sys.executable, str(script_path),
            "--course", course_name,
            "--exam", exam_name,
            "--scores-file", str(scores_file_path)
        ]
        
        # 🟢 新增：如果提供了班级名称，传递给 grader.py
        if class_name:
            cmd.extend(["--class-name", class_name])
        
        # 🟢 新增：如果提供了学生信息文件，传递给 grader.py
        if student_info_map and Path(student_info_path).exists():
            cmd.extend(["--student-info-file", str(student_info_path)])
        
        print(f"[回填] 启动命令: {' '.join(cmd)}")
        
        # 异步启动，cwd 设置为 backend 目录
        subprocess.Popen(cmd, cwd=str(backend_dir))

        return make_json_response({
            "success": True, 
            "message": f"回填脚本已启动，正在后台处理 {len(scores_map)} 名学生..."
        }, new_token=new_token)

    except Exception as e:
        print(f"[回填异常] {e}")
        return make_json_response({"success": False, "error": str(e)}, new_token=new_token), 500
if __name__ == '__main__':
    print("AI智能作业批改助手 - 后端服务")
    app.run(host='0.0.0.0', port=5000, debug=True)
