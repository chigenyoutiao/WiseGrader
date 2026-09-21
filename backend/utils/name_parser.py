import re

def parse_student_info(filename):
    """
    从文件名中提取学号和姓名

    规则：
    - 学号：提取第一段连续的数字
    - 姓名：提取第一个2-4个字的中文段，自动去除"作业"、"提交"等后缀关键词

    Args:
        filename: 文件名（如："20231001_张三.zip" 或 "张三_20231001.docx"）

    Returns:
        dict: {"student_id": "20231001", "student_name": "张三"}
    """
    # 移除文件扩展名
    name_without_ext = filename.rsplit('.', 1)[0]

    # 提取学号（第一段连续数字）
    digit_chunks = re.findall(r'\d+', name_without_ext)
    if digit_chunks:
        student_id = max(digit_chunks, key=len)  # 选最长的数字串，避免年份干扰
    else:
        student_id = "未知学号"

    # 提取所有连续的中文字符段
    chinese_segments = re.findall(r'[\u4e00-\u9fff]+', name_without_ext)

    # 需要去除的后缀关键词（按长度降序排列，优先匹配长的）
    exclude_suffixes = ['课程设计', '实验报告', '大作业', '作业', '提交', '文档', '报告', '答案', '附件', '实验', '练习', '任务']

    # 完全排除的词汇
    exclude_words = {'作业', '提交', '文档', '报告', '答案', '附件', '实验', '课程设计', '大作业', '练习', '任务', '实验报告'}

    def _clean_segment(seg: str) -> str:
        cleaned = seg
        for suffix in exclude_suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)]
        return cleaned

    # 优先从后往前找 2-4 字的姓名段（靠后的片段更可能是真名）
    student_name = "未知姓名"
    for segment in reversed(chinese_segments):
        if segment in exclude_words:
            continue
        cleaned_segment = _clean_segment(segment)
        if 2 <= len(cleaned_segment) <= 4:
            student_name = cleaned_segment
            break

    # 如果还没找到，再从前往后做更宽松的兜底
    if student_name == "未知姓名":
        for segment in chinese_segments:
            if segment in exclude_words:
                continue

            cleaned_segment = _clean_segment(segment)

            if 2 <= len(cleaned_segment) <= 4:
                student_name = cleaned_segment
                break
            elif len(cleaned_segment) > 4:
                student_name = cleaned_segment[:4]
                break
            elif len(cleaned_segment) == 1:
                continue

    # 如果还是没找到，尝试直接取第一个至少2个字的中文段（去掉完全在黑名单中的）
    if student_name == "未知姓名" and chinese_segments:
        for segment in chinese_segments:
            if segment not in exclude_words and len(segment) >= 2:
                # 仍然尝试去除后缀
                cleaned = segment
                for suffix in exclude_suffixes:
                    if cleaned.endswith(suffix):
                        cleaned = cleaned[:-len(suffix)]
                if len(cleaned) >= 2:
                    student_name = cleaned[:4]  # 最多取4个字
                    break

    return {
        "student_id": student_id,
        "student_name": student_name
    }


def test_parser():
    """测试函数"""
    test_cases = [
        "20231001_张三.zip",
        "张三_20231001.docx",
        "李四20231002作业.pdf",
        "20231003王五提交.zip",
        "赵六.docx",
        "20231004.zip"
    ]

    print("姓名解析测试:")
    for filename in test_cases:
        result = parse_student_info(filename)
        print(f"  {filename} -> 学号: {result['student_id']}, 姓名: {result['student_name']}")


if __name__ == "__main__":
    test_parser()
