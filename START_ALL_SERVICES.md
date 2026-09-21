# 🚀 启动所有服务指南

## 问题诊断
**进度条显示0/0的原因**: Redis和Celery Worker没有运行，导致异步任务无法处理，进度无法更新。

## 必需的4个服务

### 1. Redis (消息队列) ⚠️ **必需**
Windows用户需要安装 **Memurai** (Windows版Redis):

```bash
# 下载并安装Memurai:
# https://www.memurai.com/get-memurai

# 安装后会自动运行在 localhost:6379
# 检查是否运行:
memurai-cli ping
# 应该返回: PONG
```

### 2. Backend Flask API
```bash
# 终端1: 启动后端API
cd backend
python app.py
```

### 3. Celery Worker (任务处理器)
```bash
# 终端2: 启动Celery
cd backend
celery -A celery_worker worker --loglevel=info --pool=solo
```

### 4. Frontend (前端)
```bash
# 终端3: 启动前端(已在运行)
cd frontend
npm run dev
```

## 快速启动命令

### Windows (使用PowerShell)

```powershell
# 启动所有服务(需要3个终端)

# 终端1 - Backend
cd backend
python app.py

# 终端2 - Celery
cd backend
celery -A celery_worker worker --loglevel=info --pool=solo

# 终端3 - Frontend (已在运行)
cd frontend
npm run dev
```

## 验证服务运行状态

1. **Redis**: `memurai-cli ping` → 应返回 `PONG`
2. **Backend**: 访问 `http://localhost:5000` → 应返回API信息
3. **Celery**: 查看终端输出 → 应显示 "celery@xxx ready"
4. **Frontend**: 访问 `http://localhost:5173` → 应显示登录页面

## 常见问题

### Q: Memurai/Redis没有安装
A: 访问 https://www.memurai.com/get-memurai 下载安装

### Q: Celery启动失败
A: 确保Redis已运行，并使用 `--pool=solo` 参数 (Windows必需)

### Q: 进度条仍然是0/0
A: 确保Redis和Celery都在运行，然后刷新页面重新开始批改

## 服务停止

按 `Ctrl+C` 在各个终端停止对应服务
