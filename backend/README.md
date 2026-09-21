# AI智能作业批改助手 - 后端服务

## 🎯 当前版本: Phase 2 - 异步重构版

**Phase 2 已完成！** 现已支持:
- ✅ Celery + Redis 异步任务队列
- ✅ 7种真实AI模型集成（智谱、Kimi、Deepseek、QWen、ChatGPT、Claude、Doubao）
- ✅ 实时进度追踪（Redis存储）
- ✅ 非阻塞式批改（立即返回，后台处理）

**快速开始**: 查看 [PHASE2_SETUP.md](../docs/backend/PHASE2_SETUP.md) 了解详细部署步骤。

---

## 文档导航

- 查阅完整的部署与修复笔记，请访问 `docs/backend/`，其中包含所有 Phase 2 期间的特性与故障排查文档。
- 项目级说明（蓝图、提示词、协作规范）集中在 [docs/README.md](../docs/README.md) 与其子目录下，方便统一检索。

## Phase 1: 同步验证版 ✓

Phase 1 为**同步阻塞版本**，已验证核心逻辑（ZIP解压、文件读取、AI批改）正常工作。

## 安装依赖

```bash
cd backend
pip install -r requirements.txt
# 如果之前已安装依赖，请重新执行一次以获取新增的 `mammoth`（DOCX 转换）组件
```

## 运行服务

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

## 默认登录凭证

- **用户名**: `teacher`
- **密码**: `admin123`

## API 接口文档

### 1. 登录

**POST** `/api/login`

请求体:
```json
{
  "username": "teacher",
  "password": "admin123"
}
```

响应:
```json
{
  "success": true,
  "token": "..."
}
```

### 2. 上传作业包

**POST** `/api/upload/jobs`

Headers:
```
Authorization: Bearer <token>
```

请求: FormData (file字段包含ZIP文件)

响应:
```json
{
  "success": true,
  "jobId": "job_abc123",
  "studentCount": 30
}
```

### 3. 上传评分标准文件

**POST** `/api/upload/criteria-file`

Headers:
```
Authorization: Bearer <token>
```

请求: FormData (file字段包含PDF/DOCX文件)

响应:
```json
{
  "success": true,
  "criteriaText": "评分标准内容..."
}
```

### 4. 提炼评分标准

**POST** `/api/criteria/extract`

Headers:
```
Authorization: Bearer <token>
```

请求体:
```json
{
  "criteriaText": "原始评分标准..."
}
```

响应:
```json
{
  "success": true,
  "extractedPoints": "提炼后的要点..."
}
```

### 5. 开始批改（同步）

**POST** `/api/jobs/start`

Headers:
```
Authorization: Bearer <token>
```

请求体:
```json
{
  "jobId": "job_abc123",
  "model": "moonshot-v1-8k",
  "apiKey": "your-api-key",
  "gradingCriteria": "评分标准..."
}
```

> ⚠️ `model` 字段必须填写官方完整模型名（例如 `gpt-4o`, `claude-3-sonnet-20240229`, `glm-4.5`, `moonshot-v1-32k`, `deepseek-chat`, `deepseek-reasoner`, `Doubao-Seed-1.6`, `qwen3-max`, `qwen-plus`），不要再使用 `gpt`、`claude`、`kimi` 这类昵称，否则无法匹配到对应API。

> ⚠️ **豆包额外要求**：调用 Doubao 时还必须提供推理接入点 ID。请在运行服务前设置 `AI_GRADER_DOUBAO_ENDPOINT_ID=ep-xxxxxxxx`（或针对具体模型的 `AI_GRADER_DOUBAO_SEED_1_6_ENDPOINT_ID`），否则火山引擎会返回 `404 InvalidEndpoint`。

响应:
```json
{
  "success": true,
  "message": "批改任务已完成",
  "results": [...]
}
```

### 6. 查询任务状态

**GET** `/api/jobs/status/<job_id>`

Headers:
```
Authorization: Bearer <token>
```

响应:
```json
{
  "success": true,
  "status": "completed",
  "progress": {"completed": 30, "total": 30},
  "results": [
    {
      "studentId": "20231001",
      "studentName": "张三",
      "status": "completed",
      "score": 88,
      "feedback": "评语..."
    }
  ]
}
```

### 7. 导出Excel

**GET** `/api/jobs/export/<job_id>`

Headers:
``
Authorization: Bearer <token>
```

响应: Excel文件下载

### 8. 学习通下载目录导入

**POST** `/api/xxt/import`

Headers:
```
Authorization: Bearer <token>
Content-Type: application/json
```

Body 示例:
```json
{
  "directory": "E:/AgentDEV/Dev4/xuexitong/cstudy/downloads",
  "pattern": "*.zip",
  "recursive": false
}
```

若未指定 `directory`，后端会使用环境变量 `XXT_DOWNLOAD_DIR`（默认 `../xuexitong/cstudy/downloads`）自动挑选最新 ZIP 并创建任务。

### 9. 学习通脚本状态

**GET** `/api/xxt/state`

- 返回 `runner_state.json` 的内容，可用于前端展示脚本阶段、课程/考试列表、下载/上传进度。

### 10. 获取课程列表

**POST** `/api/xxt/courses`

Body（可选）：`{"sidebar": "考试"}`。
后端会调用脚本 `--list-courses`，完成后将课程数组写入状态并返回：
```json
{
  "success": true,
  "courses": [
    {"name": "区块链原理与技术 1 班"},
    {"name": "区块链原理与技术 2 班"}
  ]
}
```

### 11. 获取指定课程的考试/作业

**POST** `/api/xxt/exams`

Body：`{"course": "区块链原理与技术 1 班", "sidebar": "考试"}`（`course` 必填）。
脚本会进入该课程页面列出所有考试/作业，结果写入状态并返回。

### 12. 启动学习通脚本

**POST** `/api/xxt/start`

Body 示例：
```json
{
  "mode": "download",          // download | list_courses | list_exams
  "course": "区块链原理与技术 1 班",
  "exam": "期末考试",
  "sidebar": "考试"
}
```

- `mode = list_courses`：仅枚举课程；`list_exams` 需同时提供 `course`。
- `mode = download`：执行完整“选课 → 下载 ZIP → 自动上传”的流程，需要 `course` + `exam`。
- 接口会拒绝并返回 409 当上一次脚本仍在运行。
- 脚本运行期间可通过 `/api/xxt/state` 查看阶段与日志。



Headers:
``
Authorization: Bearer <token>
Content-Type: application/json
```

Body 示例:
```json
{
  "directory": "E:/AgentDEV/Dev4/xuexitong/cstudy/downloads",
  "pattern": "*.zip",
  "recursive": false
}
```

若未指定 `directory`，后端会使用环境变量 `XXT_DOWNLOAD_DIR`（默认 `../xuexitong/cstudy/downloads`）自动挑选最新 ZIP 并创建任务。

## 测试步骤

### 测试单个工具模块

1. 测试姓名解析:
```bash
python utils/name_parser.py
```

2. 测试AI Mock:
```bash
python utils/ai_mock.py
```

3. 测试文件读取（需要准备测试文件）:
```bash
python utils/file_reader.py
```

### 测试完整流程

1. 启动服务:
```bash
python app.py
```

2. 使用Postman或curl测试API

**示例: 登录**
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"teacher","password":"admin123"}'
```

**示例: 上传作业包**
```bash
curl -X POST http://localhost:5000/api/upload/jobs \
  -H "Authorization: Bearer <your-token>" \
  -F "file=@/path/to/jobs.zip"
```

## 项目结构

```
backend/
├── app.py                  # Flask主应用
├── config.py               # 配置文件
├── requirements.txt        # Python依赖
├── utils/                  # 工具模块
│   ├── __init__.py
│   ├── name_parser.py      # 学号姓名解析
│   ├── zip_handler.py      # ZIP文件处理（GBK支持）
│   ├── file_reader.py      # PDF/DOCX读取
│   └── ai_mock.py          # AI批改Mock函数
├── routes/                 # API路由（预留）
├── uploads/                # 上传文件存储
└── temp/                   # 临时文件存储
```

## 核心功能说明

### 1. GBK编码支持

`zip_handler.py` 中实现了对GBK编码的中文文件名的支持，解决了Windows系统下常见的中文乱码问题。

### 2. 两层ZIP处理

系统会自动：
1. 解压外层ZIP包
2. 遍历每个学生的ZIP包
3. 从文件名中提取学号和姓名
4. 解压并读取作业文件（PDF/DOCX）

### 3. Mock AI批改

Phase 1使用Mock函数模拟AI批改，返回随机分数和模拟评语。
Phase 2将替换为真实的AI API调用。

## 环境/配置

- `XXT_DOWNLOAD_DIR`: 学习通脚本下载 ZIP 的目录，默认 `../xuexitong/cstudy/downloads`。
- `XXT_STATE_FILE`: 脚本状态文件路径，默认 `../xuexitong/cstudy/runner_state.json`。
- `XXT_SCRIPT_PATH`: Selenium 脚本入口路径（若已拆分/禁用可不设置）。
- `XXT_HEADLESS`: 可选，设置为 `1/true/yes` 时强制无头模式，适合没有图形界面的服务器，避免二维码截图失败。

- XXT_DOWNLOAD_DIR: 可选，学习通脚本下载 ZIP 的目录，默认 ../xuexitong/cstudy/downloads。

## 注意事项

1. **同步阻塞**: 本版本的`/api/jobs/start`是同步的，批改大量作业时会阻塞请求。
2. **内存存储**: 任务状态存储在内存中，服务重启后会丢失。
3. **文件清理**: 上传和临时文件不会自动清理，需手动清理。

## Phase 2 升级计划

1. 引入Celery + Redis实现异步任务队列
2. 将Mock AI替换为真实API调用（支持7种AI模型）
3. 添加数据库持久化
4. 实现暂停/继续/重批改功能
5. 添加实时进度推送（WebSocket）
