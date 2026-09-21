import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Upload and temp directories
UPLOAD_FOLDER = BASE_DIR / 'uploads'
TEMP_FOLDER = BASE_DIR / 'temp'

# Ensure directories exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
TEMP_FOLDER.mkdir(exist_ok=True)

# Flask configuration
SECRET_KEY = 'dev-secret-key-change-in-production'

# Authentication (hardcoded for competition)
ADMIN_USERNAME = 'teacher'
ADMIN_PASSWORD = 'admin123'

# File size limits (100MB)
MAX_CONTENT_LENGTH = 100 * 1024 * 1024

# Allowed file extensions
# 允许的上传类型：ZIP + 常见文档/代码附件
ALLOWED_EXTENSIONS = {
    'zip', 'pdf', 'docx', 'doc', 'pptx',
    'txt', 'md', 'html', 'htm', 'rtf',
    'py', 'js', 'ts', 'java', 'c', 'cpp', 'json', 'csv', 'css'
}

# Job storage (in-memory for Phase 1)
jobs_storage = {}

# Formatting / scoring configuration
CONTENT_SCORE_WEIGHT = float(os.getenv('CONTENT_SCORE_WEIGHT', 0.8))
FORMAT_SCORE_WEIGHT = float(os.getenv('FORMAT_SCORE_WEIGHT', 0.2))

FORMAT_SCORE_RULES = {
    "heading_structure": 20,
    "paragraph_indent": 15,
    "line_spacing": 10,
    "font_size": 10,
    "figures_and_captions": 15,
    "tables_with_headers": 10,
    "headers_and_footers": 10,
    "length_requirements": 10,
}

DOCX_FORMAT_THRESHOLDS = {
    "min_indent_pt": 14,           
    "indent_target_ratio": 0.7,
    "line_spacing_range": (1.2, 1.6),
    "line_spacing_target_ratio": 0.6,
    "font_pt_range": (11, 12.5),
    "font_target_ratio": 0.6,
    "min_headings": [1, 2],
    "min_figures": 1,
    "min_tables": 1,
    "min_paragraphs": 6,
}

MAX_MARKDOWN_PREVIEW_CHARACTERS = int(os.getenv('MAX_MD_PREVIEW_CHARS', 8000))

# Xuexitong (Learning Pass) integration
DEFAULT_XXT_DIR = BASE_DIR.parent / 'xuexitong' / 'cstudy' / 'downloads'
XXT_DOWNLOAD_DIR = Path(os.getenv('XXT_DOWNLOAD_DIR', str(DEFAULT_XXT_DIR)))
XXT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
XXT_STATE_FILE = Path(os.getenv('XXT_STATE_FILE', str(BASE_DIR.parent / 'xuexitong' / 'cstudy' / 'runner_state.json')))
XXT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
XXT_SCRIPT_PATH = Path(os.getenv('XXT_SCRIPT_PATH', str(BASE_DIR.parent / 'xuexitong' / 'cstudy' / 'main.py')))
