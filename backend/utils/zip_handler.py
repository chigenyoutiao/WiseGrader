import zipfile
import os
from pathlib import Path, PurePosixPath
import chardet
from .name_parser import parse_student_info


def _safe_join(base_dir: Path, member_name: str) -> Path:
    """
    Resolve a member path within base_dir and prevent path traversal.
    """
    normalized = (member_name or "").replace("\\", "/")
    pure_path = PurePosixPath(normalized)

    if pure_path.is_absolute():
        raise ValueError("ZIP 文件包含绝对路径")

    for part in pure_path.parts:
        if part in ("", ".", ".."):
            raise ValueError("ZIP 文件包含越权路径")

    if not pure_path.parts:
        raise ValueError("ZIP 文件包含空路径")

    relative_path = Path(*pure_path.parts)
    base_resolved = base_dir.resolve()
    target_path = (base_resolved / relative_path).resolve()

    if not target_path.is_relative_to(base_resolved):
        raise ValueError("ZIP 文件包含越权路径")

    return target_path


def extract_zip_with_encoding(zip_path, extract_to, encoding='gbk'):
    """
    解压ZIP文件，支持GBK编码的中文文件名

    Args:
        zip_path: ZIP文件路径
        extract_to: 解压目标目录
        encoding: 文件名编码，默认'gbk'

    Returns:
        list: 解压后的文件路径列表
    """
    extracted_files = []
    base_extract_dir = Path(extract_to).resolve()

    try:
        # 尝试使用指定编码打开ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.filelist:
                try:
                    # 尝试用GBK解码文件名
                    try:
                        filename = file_info.filename.encode('cp437').decode(encoding)
                    except:
                        # 如果GBK失败，尝试UTF-8
                        try:
                            filename = file_info.filename.encode('cp437').decode('utf-8')
                        except:
                            # 最后使用原始文件名
                            filename = file_info.filename

                    # 构建安全的目标路径
                    try:
                        target_path = _safe_join(base_extract_dir, filename)
                    except ValueError as exc:
                        print(f"警告：跳过存在安全风险的路径 {filename}: {exc}")
                        continue

                    # 如果是目录，创建目录
                    if file_info.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        # 创建父目录
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # 解压文件
                        with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                            target.write(source.read())

                        extracted_files.append(str(target_path))

                except Exception as e:
                    print(f"警告：解压文件失败 {file_info.filename}: {e}")
                    continue

    except Exception as e:
        print(f"错误：无法打开ZIP文件 {zip_path}: {e}")
        raise

    return extracted_files


def process_double_layer_zip(outer_zip_path, temp_base_dir):
    """
    处理两层嵌套的ZIP包

    结构：
    - 外层ZIP（如：作业提交.zip）
      - 学生1.zip（常见原结构）
        - 作业.pdf / 作业.docx
      - 或者直接包含班级文件夹/学生作业文件（不再二次压缩）
        - 1班/张三_20231001.docx
        - 1班/李四20231002.pdf

    Args:
        outer_zip_path: 外层ZIP文件路径
        temp_base_dir: 临时目录基础路径

    Returns:
        list: 学生作业信息列表
        [
            {
                "student_id": "20231001",
                "student_name": "张三",
                "file_path": "/path/to/extracted/作业.pdf",
                "file_type": "pdf"
            },
            ...
        ]
    """
    students_map = {}

    def _register_student_submission(path_obj: Path, preferred_info=None):
        """统一登记一个学生作业，支持多文件并归并同一学生。"""
        info = preferred_info or parse_student_info(path_obj.name)
        key = (info["student_id"], info["student_name"])
        entry = students_map.setdefault(key, {
            "student_id": info["student_id"],
            "student_name": info["student_name"],
            "file_path": None,
            "file_type": None,
            "pptx_path": None,
            "files": []
        })

        suffix = path_obj.suffix.lower()
        file_rec = {"path": str(path_obj), "type": suffix.replace('.', '')}
        if file_rec not in entry["files"]:
            entry["files"].append(file_rec)

        doc_like = ['.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.htm', '.rtf', '.json', '.csv', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.css']

        if suffix in doc_like and not entry["file_path"]:
            entry["file_path"] = str(path_obj)
            entry["file_type"] = suffix.replace('.', '')
            print(f"[ZIP处理] 登记文档: {path_obj.name} -> {info['student_name']} ({info['student_id']})")
        elif suffix == '.pptx' and not entry["pptx_path"]:
            entry["pptx_path"] = str(path_obj)
            print(f"[ZIP处理] 登记PPTX: {path_obj.name} -> {info['student_name']} ({info['student_id']})")
        else:
            print(f"[ZIP处理] 登记附件: {path_obj.name} -> {info['student_name']} ({info['student_id']})")

    # 创建临时目录
    outer_extract_dir = Path(temp_base_dir) / "outer_layer"
    outer_extract_dir.mkdir(parents=True, exist_ok=True)

    print(f"[ZIP处理] 开始解压外层ZIP: {outer_zip_path}")

    # 第一层：解压外层ZIP
    try:
        outer_files = extract_zip_with_encoding(outer_zip_path, outer_extract_dir)
        print(f"[ZIP处理] 外层ZIP解压完成，找到 {len(outer_files)} 个文件")
    except Exception as e:
        print(f"[ZIP处理] 外层ZIP解压失败: {e}")
        raise

    # 第二层：遍历每个成员：优先处理学生ZIP，其次直接识别PDF/DOC/DOCX/PPTX
    for file_path in outer_files:
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        # 📦 老结构：学生ZIP
        if suffix == '.zip':
            student_info = parse_student_info(file_path_obj.name)
            student_id = student_info['student_id']
            student_name = student_info['student_name']

            print(f"[ZIP处理] 处理学生ZIP: {student_name} ({student_id})")

            # 创建学生专属目录
            student_extract_dir = outer_extract_dir / f"{student_id}_{student_name}"
            student_extract_dir.mkdir(parents=True, exist_ok=True)

            # 解压学生的ZIP
            try:
                student_files = extract_zip_with_encoding(file_path, student_extract_dir)
                print(f"[ZIP处理] 学生 {student_name} 的ZIP解压完成，找到 {len(student_files)} 个文件")

                # 查找作业文件（PDF/DOC/DOCX/PPTX/文本/代码）
                for student_file in student_files:
                    student_file_obj = Path(student_file)
                    if student_file_obj.suffix.lower() in ['.pdf', '.docx', '.doc', '.pptx', '.txt', '.md', '.html', '.htm', '.rtf', '.json', '.csv', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.css']:
                        _register_student_submission(student_file_obj, preferred_info=student_info)

                if not any(Path(sf).suffix.lower() in ['.pdf', '.docx', '.doc', '.pptx', '.txt', '.md', '.html', '.htm', '.rtf', '.json', '.csv', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.css'] for sf in student_files):
                    print(f"[ZIP处理] 警告：未找到学生 {student_name} 的作业文件（PDF/DOC/DOCX/PPTX/文本/代码）")

            except Exception as e:
                print(f"[ZIP处理] 学生 {student_name} 的ZIP解压失败: {e}")
                continue

        # 🆕 新结构：直接包含作业文件
        elif suffix in ['.pdf', '.docx', '.doc', '.pptx', '.txt', '.md', '.html', '.htm', '.rtf', '.json', '.csv', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.css']:
            _register_student_submission(file_path_obj)

        else:
            print(f"[ZIP处理] 跳过非作业文件: {file_path_obj.name}")

    # 输出列表，并为“只有 PPTX”场景补齐主文件字段
    students = []
    for entry in students_map.values():
        if not entry["file_path"] and entry["pptx_path"]:
            entry["file_path"] = entry["pptx_path"]
            entry["file_type"] = "pptx"
        if not entry["file_path"]:
            print(f"[ZIP处理] 警告：跳过 {entry['student_name']}，未找到可识别的作业文件")
            continue
        students.append(entry)

    print(f"[ZIP处理] 完成！共处理 {len(students)} 个学生作业")
    return students


def test_zip_handler():
    """测试ZIP处理功能"""
    print("ZIP处理器测试")
    print("注意：此测试需要真实的ZIP文件")


if __name__ == "__main__":
    test_zip_handler()
