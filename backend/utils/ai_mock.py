import time
import random


def get_ai_grading(submission_text, criteria_text, model_name, api_key):
    """
    模拟AI批改功能（Phase 1使用）

    在Phase 2时，这个函数将被替换为真实的AI API调用。

    Args:
        submission_text: 学生作业内容
        criteria_text: 评分标准
        model_name: AI模型名称（kimi, qwen, gpt-4, claude-3, deepseek, glm）
        api_key: API密钥

    Returns:
        dict: {
            "score": 88,  # 分数（0-100）
            "comment": "详细的评语..."
        }
    """
    print(f"[AI Mock] 开始模拟批改，模型: {model_name}")

    # 模拟AI思考的延迟（1-3秒）
    delay = random.uniform(1, 3)
    time.sleep(delay)

    # 生成模拟分数（60-100之间）
    mock_score = random.randint(60, 100)

    # 生成模拟评语
    submission_preview = submission_text[:50] + "..." if len(submission_text) > 50 else submission_text
    criteria_preview = criteria_text[:50] + "..." if len(criteria_text) > 50 else criteria_text

    mock_comment = f"""【模拟评语 - {model_name}】

作业内容概览：
{submission_preview}

评分依据：
{criteria_preview}

优点：
- 作业完成度较好
- 内容结构清晰
- 符合基本要求

待改进：
- 可以增加更多细节论述
- 部分内容需要进一步深化

总评：本次作业整体质量{_get_quality_level(mock_score)}，建议继续努力。
"""

    result = {
        "score": mock_score,
        "comment": mock_comment.strip()
    }

    print(f"[AI Mock] 批改完成，分数: {mock_score}")

    return result


def _get_quality_level(score):
    """根据分数返回质量等级"""
    if score >= 90:
        return "优秀"
    elif score >= 80:
        return "良好"
    elif score >= 70:
        return "中等"
    elif score >= 60:
        return "及格"
    else:
        return "不及格"


def test_ai_mock():
    """测试Mock AI功能"""
    print("\n=== AI Mock 测试 ===\n")

    submission = "这是一篇关于人工智能的作业。AI技术正在改变世界..."
    criteria = "评分标准：内容完整性30%，逻辑性30%，创新性20%，格式规范20%"

    result = get_ai_grading(submission, criteria, "kimi", "fake-api-key")

    print(f"\n分数: {result['score']}")
    print(f"评语:\n{result['comment']}")


if __name__ == "__main__":
    test_ai_mock()
