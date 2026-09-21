"""
AI Grading Module - Phase 2
支持多种AI模型的真实API调用
"""

import os
import requests
import requests.adapters
import json
import re
from requests.exceptions import ProxyError, RequestException
from requests.sessions import Session
from urllib3.util.retry import Retry


class AIGraderError(Exception):
    """AI批改错误"""
    pass


# 全局 Retry Session（自动重试503/429等错误）
retry_strategy = Retry(
    total=3,  # 最多重试3次
    backoff_factor=1,  # 重试间隔：1s, 2s, 4s
    status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码触发重试
    allowed_methods=["POST"]  # 只对POST请求重试
)

retry_session = Session()
adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
retry_session.mount("https://", adapter)
retry_session.mount("http://", adapter)

# 默认禁用系统代理，避免企业环境中配置的无效代理导致外部API调用失败
USE_SYSTEM_PROXY = os.getenv("AI_GRADER_USE_SYSTEM_PROXY", "false").lower() == "true"
retry_session.trust_env = USE_SYSTEM_PROXY
if not USE_SYSTEM_PROXY:
    print("[网络] 已禁用系统代理 (AI_GRADER_USE_SYSTEM_PROXY=false)。如需使用代理，请将该环境变量设为 true。")


def call_zhipu_api(prompt, api_key, model_name):
    """
    调用智谱AI (GLM) API
    文档: https://open.bigmodel.cn/dev/api
    """
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return {
            "content": result['choices'][0]['message']['content'],
            "usage": result.get('usage')
        }
    except ProxyError as e:
        raise AIGraderError(
            "智谱AI调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"智谱AI调用失败: {str(e)}")


def call_kimi_api(prompt, api_key, model_name):
    """
    调用Kimi (Moonshot) API
    支持模型：moonshot-v1-*, kimi-k2-*
    文档: https://platform.moonshot.cn/docs
    """
    url = "https://api.moonshot.cn/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    # 动态超时：kimi-k2-* 模型需要更长的推理时间
    if model_name.lower().startswith("kimi-k2"):
        timeout_seconds = 180  # 3分钟
        print(f"[Kimi超时] 检测到 kimi-k2 模型，使用 {timeout_seconds}s 超时")
    else:
        timeout_seconds = 60  # 默认1分钟

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
        result = response.json()
        return {
            "content": result['choices'][0]['message']['content'],
            "usage": result.get('usage')
        }
    except ProxyError as e:
        raise AIGraderError(
            "Kimi API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"Kimi API调用失败: {str(e)}")


def call_deepseek_api(prompt, api_key, model_name):
    """
    调用Deepseek API
    文档: https://platform.deepseek.com/api-docs
    """
    url = "https://api.deepseek.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return {
            "content": result['choices'][0]['message']['content'],
            "usage": result.get('usage')
        }
    except ProxyError as e:
        raise AIGraderError(
            "Deepseek API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"Deepseek API调用失败: {str(e)}")


def _resolve_doubao_endpoint_id(model_name: str):
    """
    根据模型名查找豆包推理接入点ID（endpoint id）。
    优先读取针对具体模型的配置，退化到通用环境变量。
    """
    normalized = re.sub(r'[^a-z0-9]+', '_', model_name.strip().lower())
    candidate_keys = [
        f"AI_GRADER_{normalized.upper()}_ENDPOINT_ID",
        "AI_GRADER_DOUBAO_ENDPOINT_ID",
        "DOUBAO_ENDPOINT_ID",
    ]
    for key in candidate_keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return None


def call_doubao_api(prompt, api_key, model_name):
    """
    调用火山引擎豆包 (Doubao) API
    文档: https://www.volcengine.com/docs/82312/1267862
    """
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

    endpoint_id = _resolve_doubao_endpoint_id(model_name)
    if not endpoint_id:
        raise AIGraderError(
            "豆包 API调用失败: 未配置推理接入点ID。请设置环境变量 AI_GRADER_DOUBAO_ENDPOINT_ID "
            "或针对模型的 AI_GRADER_DOUBAO_SEED_1_6_ENDPOINT_ID=ep-xxxxxxxxxx。"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Volc-Endpoint-Id": endpoint_id,
        "X-Volc-Engine-Endpoint-Id": endpoint_id,
    }

    payload = {
        "model": model_name,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        },
        "parameters": {
            "temperature": 0.7
        }
    }

    def _extract_text(choice):
        message = choice.get('message') if isinstance(choice, dict) else {}
        content = message.get('content')
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            fragments = []
            for part in content:
                if isinstance(part, dict):
                    text_value = part.get('text') or part.get('content')
                    if isinstance(text_value, str):
                        fragments.append(text_value)
                elif isinstance(part, str):
                    fragments.append(part)
            return "".join(fragments)
        return ""

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        choices = result.get('choices') or []
        if not choices:
            raise AIGraderError("豆包 API调用失败: 未返回有效内容")
        content = _extract_text(choices[0]).strip()
        if not content:
            content = json.dumps(choices[0], ensure_ascii=False)
        return {
            "content": content,
            "usage": result.get('usage')
        }
    except ProxyError as e:
        raise AIGraderError(
            "豆包 API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"豆包 API调用失败: {str(e)}")


def call_qwen_api(prompt, api_key, model_name):
    """
    调用通义千问 (QWen) API
    文档: https://help.aliyun.com/zh/dashscope/developer-reference/api-details
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "input": {
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        "parameters": {
            "temperature": 0.7
        }
    }

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        def _extract_output_text(output):
            if not output:
                return None

            if isinstance(output, dict):
                text_value = output.get('text')
                if isinstance(text_value, str):
                    return text_value

                choices = output.get('choices') or output.get('results')
                if isinstance(choices, list):
                    for choice in choices:
                        if not isinstance(choice, dict):
                            continue
                        message = choice.get('message') or {}
                        # message.content 可能是字符串或包含 text 字段的数组
                        content = message.get('content')
                        if isinstance(content, str):
                            return content
                        if isinstance(content, list):
                            fragments = []
                            for part in content:
                                if isinstance(part, dict):
                                    text_part = part.get('text') or part.get('content')
                                    if isinstance(text_part, str):
                                        fragments.append(text_part)
                                elif isinstance(part, str):
                                    fragments.append(part)
                            if fragments:
                                return '\n'.join(fragments)
                        # 部分版本会直接提供 text 字段
                        text_candidate = choice.get('text')
                        if isinstance(text_candidate, str):
                            return text_candidate

                # 少数接口直接返回 output_text
                direct = output.get('output_text') or output.get('result')
                if isinstance(direct, str):
                    return direct

            if isinstance(output, str):
                return output

            return None

        output_text = _extract_output_text(result.get('output'))
        if not output_text:
            # 记录响应以便排查，但限制长度避免日志过长
            snippet = json.dumps(result, ensure_ascii=False)[:500]
            raise AIGraderError(f"通义千问API返回格式异常，未找到文本内容: {snippet}")

        usage = result.get('usage') or result.get('token_usage')
        return {
            "content": output_text,
            "usage": usage
        }
    except AIGraderError:
        raise
    except ProxyError as e:
        raise AIGraderError(
            "通义千问API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"通义千问API调用失败: {str(e)}")


def call_openai_api(prompt, api_key, model_name):
    """
    调用OpenAI ChatGPT API
    文档: https://platform.openai.com/docs/api-reference
    """
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return {
            "content": result['choices'][0]['message']['content'],
            "usage": result.get('usage')
        }
    except ProxyError as e:
        raise AIGraderError(
            "OpenAI API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"OpenAI API调用失败: {str(e)}")


def call_claude_api(prompt, api_key, model_name):
    """
    调用Anthropic Claude API
    文档: https://docs.anthropic.com/claude/reference
    """
    url = "https://api.anthropic.com/v1/messages"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        content = result['content'][0]['text']
        return {
            "content": content,
            "usage": result.get('usage')
        }
    except ProxyError as e:
        raise AIGraderError(
            "Claude API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"Claude API调用失败: {str(e)}")


def call_gemini_api(prompt, api_key, model_name):
    """
    调用Google Gemini API
    文档: https://ai.google.dev/api/rest
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.95
        }
    }

    try:
        response = retry_session.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        content = result['candidates'][0]['content']['parts'][0]['text']
        usage = result.get('usageMetadata')
        return {
            "content": content,
            "usage": usage
        }
    except ProxyError as e:
        raise AIGraderError(
            "Gemini API调用失败: 网络代理连接失败。请检查 AI_GRADER_USE_SYSTEM_PROXY 设置或系统代理配置。"
        ) from e
    except RequestException as e:
        raise AIGraderError(f"Gemini API调用失败: {str(e)}")


def normalize_usage(raw_usage):
    """
    统一不同模型返回的token用量格式
    返回: {"promptTokens": int, "completionTokens": int, "totalTokens": int}
    """
    if not raw_usage:
        return None

    usage = raw_usage
    if isinstance(raw_usage, list):
        usage = {}
        for item in raw_usage:
            if isinstance(item, dict):
                usage.update(item)

    if not isinstance(usage, dict):
        return None

    def _to_number(value):
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return int(value)
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _pick(keys):
        for key in keys:
            if key in usage:
                candidate = _to_number(usage.get(key))
                if candidate is not None:
                    return candidate
        return None

    prompt = _pick(['prompt_tokens', 'promptTokens', 'input_tokens', 'inputTokens', 'promptTokenCount', 'inputTokenCount'])
    completion = _pick(['completion_tokens', 'completionTokens', 'output_tokens', 'outputTokens', 'candidatesTokenCount', 'outputTokenCount'])
    total = _pick(['total_tokens', 'totalTokens', 'totalTokenCount', 'usageTokens', 'allTokens'])

    if total is None and prompt is not None and completion is not None:
        total = prompt + completion

    if prompt is None and total is not None and completion is not None:
        prompt = max(total - completion, 0)

    if completion is None and total is not None and prompt is not None:
        completion = max(total - prompt, 0)

    if prompt is None and completion is None and total is None:
        return None

    normalized = {
        "promptTokens": max(prompt or 0, 0),
        "completionTokens": max(completion or 0, 0),
        "totalTokens": max(total or ((prompt or 0) + (completion or 0)), 0)
    }

    return normalized


def parse_grading_result(ai_response):
    """
    从AI响应中提取分数和评语 - 增强版，处理所有异常格式

    能处理的格式：
    1. 标准JSON: {"score": 85, "feedback": "..."}
    2. 数组格式: {"score": [90, 85], "feedback": "..."}
    3. 对象格式: {"score": {"intro": 85, "main": 90}, "feedback": "..."}
    4. 字符串格式: {"score": "85", "feedback": "..."}
    5. Markdown包裹: ```json\n{...}\n```
    6. 文本格式: 分数: 85\n评语: ...

    Args:
        ai_response: AI返回的文本

    Returns:
        dict: {"score": int, "comment": str}
    """
    original_response = ai_response

    # 步骤 1: 清理 Markdown 代码块标记
    ai_response = re.sub(r'```json\s*', '', ai_response)
    ai_response = re.sub(r'```\s*$', '', ai_response)
    ai_response = ai_response.strip()

    # 步骤 2: 尝试解析 JSON
    json_obj = None
    try:
        # 找到第一个 { 和最后一个 }
        start = ai_response.find('{')
        end = ai_response.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = ai_response[start:end+1]
            json_obj = json.loads(json_str)
    except Exception as e:
        print(f"[解析] JSON解析失败: {e}")

    # 步骤 3: 从 JSON 中提取 score（处理所有异常格式）
    if json_obj:
        score_raw = json_obj.get('score', json_obj.get('分数'))
        feedback = json_obj.get('feedback', json_obj.get('评语', original_response))

        score = None

        # 情况 1: score 是数字
        if isinstance(score_raw, (int, float)):
            score = int(score_raw)
            print(f"[解析] JSON提取分数（数字）: {score}")

        # 情况 2: score 是字符串
        elif isinstance(score_raw, str):
            try:
                score = int(float(score_raw))
                print(f"[解析] JSON提取分数（字符串转数字）: {score}")
            except:
                print(f"[解析] 警告: score 是字符串但无法转换为数字: {score_raw}")

        # 情况 3: score 是数组 - 取平均值
        elif isinstance(score_raw, list):
            try:
                numeric_values = []
                for item in score_raw:
                    if isinstance(item, (int, float)):
                        numeric_values.append(float(item))
                    elif isinstance(item, str):
                        try:
                            numeric_values.append(float(item))
                        except:
                            pass

                if numeric_values:
                    score = int(sum(numeric_values) / len(numeric_values))
                    print(f"[解析] JSON提取分数（数组平均）: {numeric_values} → {score}")
                else:
                    print(f"[解析] 警告: score 是数组但无有效数值: {score_raw}")
            except Exception as e:
                print(f"[解析] 数组处理失败: {e}")

        # 情况 4: score 是对象 - 取所有数值的平均值
        elif isinstance(score_raw, dict):
            try:
                numeric_values = []
                for key, value in score_raw.items():
                    if isinstance(value, (int, float)):
                        numeric_values.append(float(value))
                    elif isinstance(value, str):
                        try:
                            numeric_values.append(float(value))
                        except:
                            pass

                if numeric_values:
                    score = int(sum(numeric_values) / len(numeric_values))
                    print(f"[解析] JSON提取分数（对象平均）: {score_raw} → {score}")
                else:
                    print(f"[解析] 警告: score 是对象但无有效数值: {score_raw}")
            except Exception as e:
                print(f"[解析] 对象处理失败: {e}")

        if score is not None:
            return {
                "score": score,
                "comment": str(feedback)
            }

    # 步骤 4: 从文本中提取分数（正则表达式回退）
    print(f"[解析] JSON解析失败，尝试正则表达式提取")

    score = 0
    comment = original_response

    # 匹配 "分数: 85" 或 "Score: 85"
    score_patterns = [
        r'分数[：:]\s*(\d+)',
        r'score[：:]\s*(\d+)',
        r'得分[：:]\s*(\d+)',
        r'评分[：:]\s*(\d+)',
        r'成绩[：:]\s*(\d+)'
    ]

    for pattern in score_patterns:
        match = re.search(pattern, original_response, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            print(f"[解析] 正则提取分数: {score}")
            break

    # 如果没找到分数，尝试提取第一个0-100范围内的数字
    if score == 0:
        match = re.search(r'\b(\d{1,3})\b', original_response)
        if match:
            potential_score = int(match.group(1))
            if 0 <= potential_score <= 100:
                score = potential_score
                print(f"[解析] 回退提取分数（第一个0-100数字）: {score}")

    # 提取评语
    comment_patterns = [
        r'评语[：:]\s*(.+)',
        r'feedback[：:]\s*(.+)',
        r'点评[：:]\s*(.+)',
        r'建议[：:]\s*(.+)'
    ]

    for pattern in comment_patterns:
        match = re.search(pattern, original_response, re.IGNORECASE | re.DOTALL)
        if match:
            comment = match.group(1).strip()
            break

    if score == 0:
        print(f"[解析] 警告: 无法从响应中提取有效分数，使用默认值0")
        print(f"[解析] 原始响应: {original_response[:200]}...")

    return {
        "score": score,
        "comment": comment
    }


def get_ai_grading(submission_text, criteria_text, model_name, api_key, feedback_style='', grading_targets=None):
    """
    调用AI进行作业批改

    Args:
        submission_text: 学生作业内容
        criteria_text: 评分标准
        model_name: AI模型完整官方名称（例如 gpt-5, gpt-5-mini, o3, glm-4.6, glm-4.5, glm-4-plus, kimi-k2-thinking, deepseek-chat, deepseek-reasoner, doubao-seed-1.6, qwen-plus, gemini-2.5-pro, gemini-2.5-flash）
        api_key: API密钥
        feedback_style: 反馈风格（可选）
        grading_targets: 教学指标（可选）

    Returns:
        dict: {"score": int, "comment": str}
    """
    if grading_targets is None:
        grading_targets = {}

    # 构建提示词（v4：终极版，强制JSON，反惰性，反数组）
    # 构建反馈风格部分（如果提供）
    feedback_style_section = ""
    if feedback_style and feedback_style.strip():
        feedback_style_section = f"""

【反馈风格要求】
{feedback_style.strip()}
"""

    # 构建教学指标部分（如果提供）
    grading_targets_section = ""
    if grading_targets:
        targets_list = []
        if grading_targets.get('passRate'):
            targets_list.append(f"- 及格率目标（≥60分）: {grading_targets['passRate']}%")
        if grading_targets.get('excellentRate'):
            targets_list.append(f"- 优秀率目标（≥90分）: {grading_targets['excellentRate']}%")
        if grading_targets.get('minScore'):
            targets_list.append(f"- 最低分要求: {grading_targets['minScore']}分")

        if targets_list:
            grading_targets_section = f"""

【教学指标参考】
以下是本次批改需要考虑的教学指标。这些指标是整体目标，你在批改时应适当参考，但仍需基于评分标准客观评分：
{chr(10).join(targets_list)}
注意：这些指标是整体班级目标，不是单个学生的硬性要求。你应该在保持客观评分的同时，适当考虑这些教学需求。
"""

    prompt = f"""你是一位极其严格、反对"平均分"和"惰性评分"的大学教授。

【核心指令】
1. 你的目标是【精确】。在0-100范围内给出【最有理有据】的【一个总分】。
2. 【反对惰性评分】：人类评分时存在"懒惰"倾向，喜欢给80, 85, 88, 90。你【必须】克服这种倾向。
3. 【拥抱粒度】：如果一份作业根据标准真的只值87分，你就必须给87分。如果它值91分，就给91分。
4. 【合理性】：这并不是禁止你使用85分或90分。而是要求你【只有在它100%被评分标准所证明时】才使用它。
5. 【!!!格式严禁!!!】：`score` 字段【必须】是一个【数字】(Number)，【严禁】是【数组】(Array) (例如 `[90, 85]`) 或【对象】(Object) (例如 {{"item": 90}})。你必须在内部计算所有子项，最后只返回【一个总分】。
{feedback_style_section}{grading_targets_section}
【评分标准】
{criteria_text}

【学生作业】
{submission_text}

【输出格式】
你【必须】只返回一个JSON对象（不要有任何 markdown 标记或"json"字样），不要有任何其他文字。
{{
    "score": [一个0-100的【精确数字】, 必须严格遵守【核心指令 5】],
    "feedback": "[具体的评语，指出优点和需要改进的地方]"
}}
"""

    normalized_model = model_name.strip().lower()
    prefix_router = {
        "glm-": call_zhipu_api,
        "moonshot-": call_kimi_api,
        "kimi-": call_kimi_api,  # Kimi 新模型（如 kimi-k2-thinking）
        "deepseek-": call_deepseek_api,
        "doubao-": call_doubao_api,
        "qwen3-": call_qwen_api,
        "qwen-": call_qwen_api,
        "gpt-": call_openai_api,
        "o3": call_openai_api,  # OpenAI o3 模型
        "claude-": call_claude_api,
        "gemini-": call_gemini_api,
    }

    api_caller = None
    for prefix, handler in prefix_router.items():
        if normalized_model.startswith(prefix):
            api_caller = handler
            break

    if not api_caller:
        valid_prefixes = ", ".join(prefix_router.keys())
        raise AIGraderError(
            f"不支持的AI模型: {model_name}。模型名必须以以下前缀之一开头: {valid_prefixes}，并使用官方完整型号（如 gpt-5、gpt-5-mini、o3、glm-4.6、glm-4.5、glm-4-plus、kimi-k2-thinking、deepseek-chat、deepseek-reasoner、doubao-seed-1.6、qwen3-max、qwen-plus、gemini-2.5-pro、gemini-2.5-flash）。"
        )

    print(f"[AI批改] 使用模型: {model_name}")

    # 调用AI API
    try:
        ai_response = api_caller(prompt, api_key, model_name)
        if isinstance(ai_response, dict) and 'content' in ai_response:
            response_text = ai_response['content']
            usage_details = normalize_usage(ai_response.get('usage'))
        else:
            response_text = str(ai_response)
            usage_details = None

        print(f"[AI批改] AI响应: {response_text[:200]}...")
        if usage_details:
            print(
                f"[AI批改] Token消耗 -> prompt: {usage_details['promptTokens']}, "
                f"completion: {usage_details['completionTokens']}, total: {usage_details['totalTokens']}"
            )

        # 解析结果
        result = parse_grading_result(response_text)

        # 验证分数范围
        if not (0 <= result['score'] <= 100):
            print(f"[AI批改] 警告: 分数超出范围 {result['score']}, 修正为0-100")
            result['score'] = max(0, min(100, result['score']))

        print(f"[AI批改] 批改完成，分数: {result['score']}")
        return {
            "score": result['score'],
            "comment": result['comment'],
            "token_usage": usage_details
        }

    except AIGraderError:
        raise
    except Exception as e:
        raise AIGraderError(f"AI批改失败: {str(e)}")


def test_ai_grader():
    """测试AI批改功能"""
    print("AI批改测试")

    test_submission = """
    本次实验主要研究了Python中的面向对象编程。
    我实现了一个学生管理系统，包含Student类和Course类。
    代码运行正常，实现了所有要求的功能。
    """

    test_criteria = """
    1. 代码实现完整性 (40分)
    2. 代码质量和规范 (30分)
    3. 功能测试和文档 (30分)
    """

    # 注意: 需要真实的API Key才能测试
    print("注意: 本测试需要真实的API Key")
    print(f"测试作业长度: {len(test_submission)} 字符")
    print(f"评分标准: {test_criteria}")


if __name__ == "__main__":
    test_ai_grader()
