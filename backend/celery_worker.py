"""
Celery Worker - Phase 2
异步任务处理器
"""

from celery import Celery
import time
from pathlib import Path

from utils.file_reader import read_file_content
from utils.ai_grader import get_ai_grading, AIGraderError
from utils.job_store import get_job, save_job, REDIS_AVAILABLE
from utils.doc_parser import evaluate_docx_formatting
from utils.pptx_reader import read_pptx
import config

# 创建Celery应用
celery_app = Celery(
    'grading_worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10分钟超时
    worker_prefetch_multiplier=1,  # 一次只取一个任务
    task_ignore_result=True,  # 结果持久化由自定义存储处理，避免依赖Redis backend
)

# 创建Redis客户端（用于状态存储）
# AI调用失败时针对单个学生的自动重试配置
MAX_AI_ATTEMPTS = 2  # 第一次失败后再重试一次
AI_RETRY_BACKOFF_SECONDS = 5  # 重试前的等待时间
LONG_THINK_MODEL_HINTS = ('kimi-k2', 'deepseek-r1', 'r1-zero', 'longthink')
DOC_WEIGHT = 0.6
PPTX_WEIGHT = 0.4
DOC_LIKE_EXTS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.htm', '.rtf', '.json', '.csv', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.css'}


def _count_completed(results):
    return sum(
        1
        for item in results
        if item.get('status') in ('completed', 'failed')
    )



def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def update_job_status(job_id, status=None, progress=None, results=None):
    """更新任务状态到存储（Redis 不可用时回退内存）。"""
    job = get_job(job_id)

    if not job:
        job = {
            "job_id": job_id,
            "status": "uploaded",
            "progress": {"completed": 0, "total": 0},
            "results": []
        }

    if status is not None:
        job['status'] = status

    if progress is not None:
        job['progress'] = progress

    if results is not None:
        job['results'] = results

    save_job(job_id, job)
    backend = "Redis" if REDIS_AVAILABLE else "内存"
    print(f"[存储] 任务状态已更新 ({backend}): {job_id} -> {job['status']}, 进度: {job['progress']}")



def append_job_result(job_id, result):
    """将单个学生的批改结果写入存储（如存在则覆盖）"""
    job = get_job(job_id)

    if not job:
        print(f"[存储] 警告: 任务 {job_id} 不存在，无法追加结果")
        return

    results = job.setdefault('results', [])
    student_id = result.get('studentId') or result.get('student_id')

    existing_index = next(
        (
            idx
            for idx, item in enumerate(results)
            if (item.get('studentId') or item.get('student_id')) == student_id
        ),
        None,
    )

    if existing_index is not None:
        results[existing_index] = {**results[existing_index], **result}
    else:
        results.append(result)

    progress = job.setdefault('progress', {})
    progress['completed'] = _count_completed(results)
    progress.setdefault('total', len(job.get('students', [])))

    save_job(job_id, job)
    backend = "Redis" if REDIS_AVAILABLE else "内存"
    print(
        f"[存储] 结果已更新({backend}): {result['studentName']} 进度 "
        f"{progress['completed']}/{progress['total']}"
    )




def _resolve_attempts_for_model(model_name: str) -> int:
    lowered = (model_name or '').lower()
    if any(hint in lowered for hint in LONG_THINK_MODEL_HINTS):
        return MAX_AI_ATTEMPTS + 1
    return MAX_AI_ATTEMPTS


@celery_app.task(bind=True, name='tasks.grade_job')
def grade_job(self, job_id, model_name, api_key, grading_criteria, feedback_style='', grading_targets=None, target_student_ids=None):
    """
    批改任务的Celery任务

    Args:
        job_id: 任务ID
        model_name: AI模型名称
        api_key: API密钥
        grading_criteria: 评分标准
        feedback_style: 反馈风格（可选）
        grading_targets: 教学指标（可选）

    Returns:
        dict: 任务完成状态
    """
    if grading_targets is None:
        grading_targets = {}
    print(f"\n{'='*60}")
    print(f"[Celery任务] 开始批改任务: {job_id}")
    print(f"[Celery任务] 模型: {model_name}")
    print(f"{'='*60}\n")

    try:
        # 读取任务信息（Redis / 内存）
        job = get_job(job_id)

        if not job:
            error_msg = f"任务 {job_id} 不存在"
            print(f"[Celery任务] 错误: {error_msg}")
            return {"success": False, "error": error_msg}

        students = job.get('students', [])
        if target_student_ids:
            target_set = {str(target_id) for target_id in target_student_ids}
            students = [
                student for student in students
                if str(student.get('student_id')) in target_set
            ]


        if not students:
            error_msg = "没有找到学生作业"
            print(f"[Celery任务] 错误: {error_msg}")
            update_job_status(job_id, status="failed")
            return {"success": False, "error": error_msg}


        total_students = len(students)
        print(f"[Celery任务] 共{total_students} 个学生作业需要批改\n")

        overall_total = job.get('progress', {}).get('total') or len(job.get('students', []))
        completed_before = _count_completed(job.get('results', []))

        update_job_status(
            job_id,
            status="processing",
            progress={"completed": completed_before, "total": overall_total}
        )

        # 逐个批改学生作业
        attempts_allowed = _resolve_attempts_for_model(model_name)

        for idx, student in enumerate(students, 1):
            student_name = student['student_name']
            student_id = student['student_id']
            files = student.get("files") or []
            legacy_file = student.get('file_path')
            legacy_pptx = student.get('pptx_path')
            if not files:
                if legacy_file:
                    files.append({"path": legacy_file, "type": Path(legacy_file).suffix.lower().replace('.', '')})
                if legacy_pptx and (not legacy_file or Path(legacy_pptx) != Path(legacy_file)):
                    files.append({"path": legacy_pptx, "type": Path(legacy_pptx).suffix.lower().replace('.', '')})

            print(f"\n[批改进度] {idx}/{total_students} - {student_name} ({student_id})")

            formatting_payload = None
            formatting_preview_format = None
            doc_scores = {
                "content": None,
                "formatting": None,
                "final": None,
            }
            pptx_score = None
            pptx_metrics = None
            doc_feedback = None
            pptx_feedback = None
            token_usage = None
            items = []

            try:
                results_per_file = []

                # 读取并分类所有文件
                for f in files:
                    fpath = Path(f.get("path", ""))
                    if not fpath.exists():
                        print(f"[批改] 跳过不存在的文件: {fpath}")
                        continue
                    suffix = fpath.suffix.lower()
                    kind = 'pptx' if suffix == '.pptx' else 'doc'

                    try:
                        if kind == 'pptx':
                            pptx_payload = read_pptx(fpath)
                            pptx_metrics = pptx_payload.get("metrics", {})
                            pptx_text = pptx_payload.get("text", "")

                            metrics_str = (
                                f"【PPTX客观指标】共{pptx_metrics.get('slide_count', 0)}页；"
                                f"图片{pptx_metrics.get('picture_count', 0)}；"
                                f"媒体{pptx_metrics.get('media_count', 0)}；"
                                f"表格{pptx_metrics.get('table_count', 0)}；"
                                f"图表{pptx_metrics.get('chart_count', 0)}；"
                                f"切换页数{pptx_metrics.get('transition_slides', 0)}；"
                                f"动画/时间线页数{pptx_metrics.get('timing_slides', 0)}；"
                                f"检测到动画/切换: {pptx_metrics.get('has_animation_or_transition')}"
                            )

                            submission = (
                                f"【PPTX幻灯片文本】\n{pptx_text}\n\n"
                                f"{metrics_str}\n"
                                "请重点考察演示性、多媒体/图表使用、版式设计；如缺少图片/媒体/动画则应降低该部分得分。"
                            )

                            grading_result = None
                            for attempt in range(1, attempts_allowed + 1):
                                print(f"[批改] 调用AI批改（PPTX: {fpath.name}）... (attempt {attempt}/{attempts_allowed})")
                                try:
                                    grading_result = get_ai_grading(
                                        submission_text=submission,
                                        criteria_text=grading_criteria,
                                        model_name=model_name,
                                        api_key=api_key,
                                        feedback_style=feedback_style,
                                        grading_targets=grading_targets
                                    )
                                    break
                                except AIGraderError as ai_error:
                                    print(f"[批改] PPTX AI 调用失败，第 {attempt} 次尝试: {ai_error}")
                                    if attempt < attempts_allowed:
                                        print(f"[批改] 等待 {AI_RETRY_BACKOFF_SECONDS}s 后重试...")
                                        time.sleep(AI_RETRY_BACKOFF_SECONDS)
                                    else:
                                        raise ai_error

                            score_val = _to_float(grading_result.get('score') if grading_result else None)
                            results_per_file.append({
                                "kind": "pptx",
                                "name": fpath.name,
                                "score": score_val,
                                "feedback": grading_result.get('comment') if grading_result else None,
                                "metrics": pptx_metrics,
                            })
                            pptx_score = score_val
                            pptx_feedback = grading_result.get('comment') if grading_result else None

                        else:
                            content = read_file_content(fpath)
                            if not content or len(content.strip()) < 5:
                                print(f"[批改] 文件内容过短，跳过: {fpath}")
                                continue

                            if suffix == '.docx' and formatting_payload is None:
                                try:
                                    formatting_payload = evaluate_docx_formatting(str(fpath))
                                    if formatting_payload.get('markdown'):
                                        formatting_preview_format = 'markdown'
                                except Exception as format_exc:
                                    print(f"[格式] DOCX 格式解析失败: {format_exc}")

                            submission = f"【文件：{fpath.name}】\n{content}"

                            grading_result = None
                            for attempt in range(1, attempts_allowed + 1):
                                print(f"[批改] 调用AI批改（文档: {fpath.name}）... (attempt {attempt}/{attempts_allowed})")
                                try:
                                    grading_result = get_ai_grading(
                                        submission_text=submission,
                                        criteria_text=grading_criteria,
                                        model_name=model_name,
                                        api_key=api_key,
                                        feedback_style=feedback_style,
                                        grading_targets=grading_targets
                                    )
                                    break
                                except AIGraderError as ai_error:
                                    print(f"[批改] AI调用失败，第 {attempt} 次尝试: {ai_error}")
                                    if attempt < attempts_allowed:
                                        print(f"[批改] 等待 {AI_RETRY_BACKOFF_SECONDS}s 后重试...")
                                        time.sleep(AI_RETRY_BACKOFF_SECONDS)
                                    else:
                                        raise ai_error

                            token_usage = grading_result.get('token_usage')
                            content_score = _to_float(grading_result.get('score'))
                            doc_scores["content"] = content_score if doc_scores["content"] is None else doc_scores["content"]
                            doc_scores["formatting"] = _to_float(formatting_payload.get('score') if formatting_payload else None)
                            doc_scores["final"] = content_score
                            results_per_file.append({
                                "kind": "doc",
                                "name": fpath.name,
                                "score": content_score,
                                "feedback": grading_result.get('comment') if grading_result else None,
                            })
                            if grading_result.get('comment'):
                                doc_feedback = grading_result.get('comment')

                    except Exception as exc:
                        print(f"[批改] 处理文件失败 {fpath}: {exc}")
                        continue

                # 计算权重：如果有多文件且未提供权重，则平均分配
                scored_items = [item for item in results_per_file if item.get("score") is not None]
                if not scored_items:
                    raise Exception("未能获取任何可用评分")

                equal_weight = 1 / len(scored_items)
                weights = {i: equal_weight for i in range(len(scored_items))}

                total_weight = sum(weights.values())
                weighted_sum = sum(item["score"] * weights[idx] for idx, item in enumerate(scored_items))
                if total_weight > 0:
                    final_score = round(weighted_sum / total_weight, 2)
                else:
                    final_score = None
                final_score_int = int(round(final_score)) if final_score is not None else None

                doc_scores_list = [it["score"] for it in scored_items if it["kind"] == "doc" and it.get("score") is not None]
                pptx_scores_list = [it["score"] for it in scored_items if it["kind"] == "pptx" and it.get("score") is not None]
                doc_scores["content"] = round(sum(doc_scores_list) / len(doc_scores_list), 2) if doc_scores_list else None
                doc_scores["final"] = doc_scores["content"]
                pptx_score = round(sum(pptx_scores_list) / len(pptx_scores_list), 2) if pptx_scores_list else None

                doc_weight_out = round(sum(weights[idx] for idx, item in enumerate(scored_items) if item["kind"] == "doc"), 2)
                pptx_weight_out = round(sum(weights[idx] for idx, item in enumerate(scored_items) if item["kind"] == "pptx"), 2)

                feedback_parts = []
                for item in scored_items:
                    if item.get("feedback"):
                        label = "PPTX反馈" if item["kind"] == "pptx" else "文档反馈"
                        feedback_parts.append(f"[{label} - {item['name']}]\n{item['feedback']}")

                result = {
                    "studentId": student_id,
                    "studentName": student_name,
                    "status": "completed",
                    "score": final_score_int if final_score_int is not None else (doc_scores["final"] or pptx_score),
                    "contentScore": doc_scores["content"],
                    "formattingScore": doc_scores["formatting"],
                    "formattingChecks": (formatting_payload.get('checks') if formatting_payload else []),
                    "formattingPreview": (formatting_payload.get('markdown') if formatting_payload else None),
                    "formattingPreviewFormat": formatting_preview_format,
                    "formattingConfidence": formatting_payload.get('confidence') if formatting_payload else None,
                    "formattingMetrics": formatting_payload.get('metrics') if formatting_payload else None,
                    "feedback": "\n\n".join(feedback_parts),
                    "docFinalScore": doc_scores["final"],
                    "pptxScore": pptx_score,
                    "pptxMetrics": pptx_metrics,
                    "pptxFeedback": pptx_feedback,
                    "docWeight": doc_weight_out,
                    "pptxWeight": pptx_weight_out,
                    "tokenUsage": token_usage,
                    "model": model_name
                }

                print(
                    f"[批改] ✓ 批改完成 - 总分: {result['score']}, 文件数: {len(scored_items)}"
                )

            except AIGraderError as e:
                # AI调用失败
                print(f"[批改] ✗ AI批改失败: {e}")
                result = {
                    "studentId": student_id,
                    "studentName": student_name,
                    "status": "failed",
                    "score": None,
                    "contentScore": doc_scores.get("content"),
                    "formattingScore": (_to_float(formatting_payload.get('score')) if formatting_payload else None),
                    "formattingChecks": (formatting_payload.get('checks') if formatting_payload else []),
                    "formattingPreview": (formatting_payload.get('markdown') if formatting_payload else None),
                    "formattingPreviewFormat": formatting_preview_format,
                    "formattingConfidence": formatting_payload.get('confidence') if formatting_payload else None,
                    "formattingMetrics": formatting_payload.get('metrics') if formatting_payload else None,
                    "feedback": f"AI批改失败: {str(e)}",
                    "docFinalScore": doc_scores.get("final"),
                    "pptxScore": pptx_score,
                    "pptxMetrics": pptx_metrics,
                    "docWeight": locals().get("doc_weight", DOC_WEIGHT if (locals().get("submission_text") or doc_scores.get("content")) else 0),
                    "pptxWeight": locals().get("pptx_weight", PPTX_WEIGHT if locals().get("pptx_paths") else 0),
                    "tokenUsage": None,
                    "model": model_name
                }

            except Exception as e:
                # 其他错误
                print(f"[批改] ✗ 批改失败: {e}")
                result = {
                    "studentId": student_id,
                    "studentName": student_name,
                    "status": "failed",
                    "score": None,
                    "contentScore": doc_scores.get("content"),
                    "formattingScore": (_to_float(formatting_payload.get('score')) if formatting_payload else None),
                    "formattingChecks": (formatting_payload.get('checks') if formatting_payload else []),
                    "formattingPreview": (formatting_payload.get('markdown') if formatting_payload else None),
                    "formattingPreviewFormat": formatting_preview_format,
                    "formattingConfidence": formatting_payload.get('confidence') if formatting_payload else None,
                    "formattingMetrics": formatting_payload.get('metrics') if formatting_payload else None,
                    "feedback": f"批改失败: {str(e)}",
                    "docFinalScore": doc_scores.get("final"),
                    "pptxScore": pptx_score,
                    "pptxMetrics": pptx_metrics,
                    "docWeight": locals().get("doc_weight", DOC_WEIGHT if (locals().get("submission_text") or doc_scores.get("content")) else 0),
                    "pptxWeight": locals().get("pptx_weight", PPTX_WEIGHT if locals().get("pptx_paths") else 0),
                    "tokenUsage": None,
                    "model": model_name
                }

            # 追加结果到Redis
            append_job_result(job_id, result)

            # 更新任务进度（通过Celery的meta）
            try:
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx,
                        'total': total_students,
                        'status': f'批改中: {student_name}'
                    }
                )
            except Exception as state_exc:
                print(f"[Celery任务] 警告: 更新任务进度到backend失败: {state_exc}")

            # [v2 速率限制] 仅对 Gemini 模型（免费层）进行速率限制
            if "gemini-" in model_name.lower():
                print(f"[速率限制] 检测到Gemini模型 ({model_name})，强制休眠10秒以避免429/503错误...")
                time.sleep(10)

        # 所有作业批改完成
        update_job_status(job_id, status="completed")

        print(f"\n{'='*60}")
        print(f"[Celery任务] ✓ 任务 {job_id} 批改完成！")
        print(f"{'='*60}\n")

        return {
            "success": True,
            "message": "批改任务已完成",
            "total": total_students
        }

    except Exception as e:
        error_msg = f"任务执行失败: {str(e)}"
        print(f"\n[Celery任务] ✗ 错误: {error_msg}\n")

        # 更新状态为失败
        update_job_status(job_id, status="failed")

        return {
            "success": False,
            "error": error_msg
        }


@celery_app.task(name='tasks.test_connection')
def test_connection():
    """测试Celery连接"""
    print("[Celery测试] 连接正常！")
    return {"status": "ok", "message": "Celery worker is running"}


if __name__ == "__main__":
    print("Celery Worker - 启动说明")
    print("="*60)
    print("请使用以下命令启动Celery worker:")
    print("")
    print("  celery -A celery_worker worker --loglevel=info --pool=solo")
    print("")
    print("注意:")
    print("1. 确保Redis (Memurai) 已在 localhost:6379 运行")
    print("2. Windows下必须使用 --pool=solo 参数")
    print("="*60)
