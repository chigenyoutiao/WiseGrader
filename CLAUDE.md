# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI智能作业批改助手** - An AI-powered assignment grading assistant for educators. The system processes nested ZIP archives containing student submissions (PDF/DOCX), applies AI-based grading using multiple LLM providers, and exports results to Excel.

**Tech Stack:**
- **Backend**: Flask + Celery + Redis (Python 3.x)
- **Frontend**: React + TypeScript + Vite + Tailwind CSS + Zustand
- **Architecture**: Async task queue processing with polling-based progress updates

## Essential Commands

### Development Setup

**Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### Running the Application

**Required Services (must run in 4 separate terminals):**

1. **Redis** (required for task queue):
   - Windows: Install Memurai from https://www.memurai.com/get-memurai (auto-starts on port 6379)
   - Verify: `memurai-cli ping` should return `PONG`

2. **Backend Flask API** (Terminal 1):
   ```bash
   cd backend
   python app.py
   ```
   Server runs at http://localhost:5000

3. **Celery Worker** (Terminal 2):
   ```bash
   cd backend
   celery -A celery_worker worker --loglevel=info --pool=solo
   ```
   Note: `--pool=solo` is **mandatory** on Windows

4. **Frontend** (Terminal 3):
   ```bash
   cd frontend
   npm run dev
   ```
   Dev server runs at http://localhost:5173

### Testing & Building

**Backend:**
- Manual tests: `python backend/test_*.py` (no pytest framework)
- Test individual utils: `python utils/name_parser.py`, `python utils/ai_mock.py`

**Frontend:**
- Lint: `npm run lint`
- Build: `npm run build` (runs TypeScript check + production build)
- Preview: `npm run preview`

## Architecture & Key Concepts

### Data Flow Pipeline

1. **Upload**: Teacher uploads nested ZIP (outer contains student ZIPs)
2. **Parse**: `utils/zip_handler.py` handles two-layer extraction with GBK encoding support
3. **Extract**: Student ID/name parsed from filenames using regex (numbers=ID, Chinese=name)
4. **Queue**: Job stored in Redis (or in-memory fallback), Celery tasks created
5. **Grade**: Worker processes each student file via `utils/ai_grader.py` calling configured LLM
6. **Poll**: Frontend polls `/api/jobs/status/:jobId` every 3-5 seconds for progress
7. **Export**: Generate Excel via `/api/jobs/export/:jobId`

### Task Queue Architecture

- **Synchronous fallback**: If Celery worker unavailable, uses background threads
- **Progress tracking**: Redis stores job state with `job:<jobId>` keys
- **Partial retry**: `/api/jobs/retry` endpoint accepts `studentIds` array to re-grade specific students
- **Deduplication**: Results merged by `studentId` in frontend store (`src/store.ts`)

### AI Model Integration

Supports 7 LLM providers via `utils/ai_grader.py`:
- 智谱AI (GLM): `glm-4.5`, `glm-4`
- Kimi/Moonshot: `moonshot-v1-8k`, `moonshot-v1-32k`, `kimi-k2-*`
- Deepseek: `deepseek-chat`, `deepseek-reasoner`
- QWen: `qwen3-max`, `qwen-plus`
- OpenAI: `gpt-4o`, `gpt-4-turbo`
- Anthropic Claude: `claude-3-sonnet-20240229`, etc.
- Doubao (火山引擎): `Doubao-Seed-1.6` (requires `AI_GRADER_DOUBAO_ENDPOINT_ID` env var)

**Important**: Model names must be exact API model IDs (not nicknames like "gpt" or "claude")

### File Processing

- **ZIP Handling**: `utils/zip_handler.py` - GBK encoding support for Chinese filenames
- **Document Reading**: `utils/file_reader.py` - PDF (pdfplumber) and DOCX (python-docx, mammoth)
- **Formatting Checks**: `utils/doc_parser.py` - DOCX structure validation (headings, spacing, indents)
- **Name Parsing**: `utils/name_parser.py` - Regex extraction of student ID (digits) and name (Chinese chars)

## Critical Implementation Details

### Student ID/Name Extraction

Must extract separately into different fields:
- **Student ID**: Numeric characters only
- **Student Name**: Chinese characters only
- Regex pattern used in `name_parser.py` handles various formats like `20231001_张三.zip`

### GBK Encoding for Windows

`zip_handler.py` uses `chardet` and explicit GBK decoding to handle Chinese filenames in ZIPs created on Windows systems.

### API Field Naming

- **Backend JSON**: camelCase (`jobId`, `apiKey`, `gradingCriteria`)
- **Python code**: snake_case (`job_id`, `api_key`, `grading_criteria`)
- Conversion happens in API layer (`app.py`)

### Progress Update Pattern

Frontend must **poll** (not WebSocket) because Phase 2 uses polling architecture:
```typescript
// src/store.ts polls /api/jobs/status/:jobId
setInterval(() => fetchJobStatus(jobId), 3000)
```

### Formatting Score Integration

Content scoring (AI) and formatting scoring (structural analysis) are weighted:
```python
# config.py
CONTENT_SCORE_WEIGHT = 0.8  # 80%
FORMAT_SCORE_WEIGHT = 0.2   # 20%
```

### Environment Variables

- `XXT_DOWNLOAD_DIR`: Path to Xuexitong download folder (default: `../xuexitong/cstudy/downloads`)
- `AI_GRADER_DOUBAO_ENDPOINT_ID`: Required for Doubao models
- `AI_GRADER_USE_SYSTEM_PROXY`: Set to "true" to enable proxy (default: disabled)
- `CONTENT_SCORE_WEIGHT`, `FORMAT_SCORE_WEIGHT`: Score composition weights

## Code Organization

### Backend Structure
```
backend/
├── app.py                 # Flask routes & auth
├── celery_worker.py       # Celery tasks (grade_job)
├── config.py              # Settings & constants
├── utils/
│   ├── ai_grader.py       # Multi-provider LLM calls
│   ├── ai_mock.py         # Mock grading (Phase 1)
│   ├── doc_parser.py      # DOCX formatting checks
│   ├── file_reader.py     # PDF/DOCX text extraction
│   ├── job_store.py       # Redis/in-memory persistence
│   ├── name_parser.py     # Student ID/name regex
│   └── zip_handler.py     # Two-layer ZIP processing
├── uploads/               # Job ZIP files
└── temp/                  # Extraction workspace
```

### Frontend Structure
```
frontend/src/
├── main.tsx              # Entry point
├── App.tsx               # Main app component
├── api.ts                # Axios API client
├── store.ts              # Zustand state management
├── pages/
│   └── LoginPage.tsx
├── components/
│   ├── ControlPanel.tsx  # Left sidebar
│   ├── WorkflowContainer.tsx  # Right content area
│   ├── Upload.tsx        # File upload step
│   ├── Criteria.tsx      # Grading criteria step
│   ├── Config.tsx        # Model config step
│   ├── Actions.tsx       # Start/retry buttons
│   ├── JobTable.tsx      # Results table
│   ├── Dashboard.tsx     # Statistics view
│   ├── FeedbackStyle.tsx # Feedback customization
│   └── GradingTargets.tsx # Teaching objectives
└── layouts/              # Layout components
```

## API Endpoints Reference

**Authentication:**
- `POST /api/login` - Returns JWT token for `teacher/admin123`

**Upload:**
- `POST /api/upload/jobs` - Upload ZIP, returns `jobId`
- `POST /api/upload/criteria-file` - Upload PDF/DOCX criteria
- `POST /api/xxt/import` - Import from Xuexitong download directory

**Grading:**
- `POST /api/criteria/extract` - Extract key points from criteria text
- `POST /api/jobs/start` - Start grading job (requires `jobId`, `model`, `apiKey`, `gradingCriteria`)
- `POST /api/jobs/retry` - Retry specific students (requires `studentIds` array)

**Status:**
- `GET /api/jobs/status/:jobId` - Poll for progress and results
- `GET /api/jobs/export/:jobId` - Download Excel report

## Common Development Patterns

### Adding a New AI Provider

1. Add API call function in `utils/ai_grader.py` (e.g., `call_newprovider_api`)
2. Add routing logic in `get_ai_grading()` based on model name prefix
3. Update docs and example model names in `backend/README.md`
4. Test with `backend/test_modules.py` or manual API calls

### Modifying Grading Prompt

AI prompts are constructed in `celery_worker.py` in the `grade_job` task:
- Includes criteria, content, and explicit instruction to avoid lazy scoring
- Returns JSON with `score` (integer) and `feedback` (string)

### Frontend State Updates

State managed via Zustand in `src/store.ts`:
- `uploadJobFile()` - Handles ZIP upload
- `startGrading()` - Initiates job
- `fetchJobStatus()` - Polling function
- Results are merged by `studentId` to support partial retries

## Debugging Tips

**"0/0 Progress" Issue:**
- Verify Redis is running: `memurai-cli ping`
- Check Celery worker is running with `--pool=solo`
- Look for worker logs showing task receipt

**GBK Encoding Errors:**
- Ensure `chardet` is installed
- Check `zip_handler.py` uses `encoding='gbk'` fallback

**AI API Failures:**
- Check `AI_GRADER_USE_SYSTEM_PROXY` if behind corporate proxy
- Verify API key format and model name exactness
- Review retry logic in `celery_worker.py` (MAX_AI_ATTEMPTS=2)

**Frontend-Backend Mismatch:**
- Ensure camelCase in API JSON matches snake_case conversion in `app.py`
- Check `api.ts` request/response types match backend schemas

## Testing Workflow

1. Start all 4 services (Redis, Backend, Celery, Frontend)
2. Login with `teacher/admin123`
3. Upload test ZIP (nested structure: `outer.zip` containing `学号_姓名.zip` files)
4. Upload or paste grading criteria
5. Configure AI model and API key
6. Click "Start Grading"
7. Observe progress updates in table
8. Export to Excel when complete
9. Test partial retry by selecting specific students

## Important Notes

- **Windows-specific**: Always use `--pool=solo` for Celery on Windows
- **Synchronous fallback**: System degrades gracefully without Redis/Celery (uses threads)
- **No WebSocket**: Progress updates use HTTP polling, not real-time sockets
- **In-memory fallback**: Job storage falls back to `config.jobs_storage` dict if Redis unavailable
- **Commit conventions**: Use `feat:`, `fix:`, `refactor:`, `chore:`, `docs:` prefixes
- **Branch naming**: `feat/...`, `fix/...`, `refactor/...`

## Documentation References

- Backend detailed docs: `backend/README.md` and `docs/backend/`
- Project blueprint: `docs/project_blueprint.zh.md`
- Service startup guide: `START_ALL_SERVICES.md`
- Agent collaboration rules: `AGENTS.md`
- Phase 2 deployment: `docs/backend/PHASE2_SETUP.md`
