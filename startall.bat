@echo off
setlocal enabledelayedexpansion

:: 1. 获取当前目录
set "BASE_DIR=%~dp0"
set "FRONTEND_DIR=%BASE_DIR%frontend"
set "BACKEND_DIR=%BASE_DIR%backend"

:: ================= 配置区 =================
:: 请在这里确认你的虚拟环境文件夹名字是 .venv 还是 venv
set "VENV_NAME=.venv"
:: =========================================

set "VENV_ACTIVATE=%BACKEND_DIR%\%VENV_NAME%\Scripts\activate.bat"

echo.
echo [检查环境]
echo 前端目录: "%FRONTEND_DIR%"
echo 后端目录: "%BACKEND_DIR%"
echo 虚拟环境: "%VENV_ACTIVATE%"

:: 检查虚拟环境是否存在，不存在则报错暂停
if not exist "%VENV_ACTIVATE%" (
    echo.
    echo [错误] 找不到虚拟环境启动脚本！
    echo 请检查 backend 目录下是否有 "%VENV_NAME%" 文件夹。
    echo 如果你的环境叫 "venv"，请右键编辑此脚本，修改 VENV_NAME=.venv 为 VENV_NAME=venv
    pause
    exit
)

echo.
echo ===== 正在启动三个服务... =====

:: 1. 启动前端 (使用双引号包裹路径防止空格报错)
start "Frontend (React)" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

:: 2. 启动后端 Flask
start "Backend (Flask API)" cmd /k "cd /d "%BACKEND_DIR%" && call "%VENV_ACTIVATE%" && python app.py"

:: 3. 启动 Celery Worker (使用 python -m celery 更稳定)
start "Backend (Celery Worker)" cmd /k "cd /d "%BACKEND_DIR%" && call "%VENV_ACTIVATE%" && python -m celery -A celery_worker worker --loglevel=info --pool=solo"

echo.
echo [成功] 所有窗口已尝试启动。
echo 如果有窗口闪退，请检查该窗口内的报错信息。
timeout /t 3 >nul
exit