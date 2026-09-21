# 文件路径: backend/xxt/browser.py
import platform
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def create_driver(headless=False, download_dir=None):
    """创建并配置 Chrome 浏览器驱动"""
    opts = Options()
    
    # 1. 系统环境适配
    if platform.system() == 'Linux':
        opts.binary_location = "/usr/bin/google-chrome"
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        headless = True # Linux 强制无头
    else:
        # ⚠️ 请确认你的 Chrome 路径
        opts.binary_location = r"D:\SoftWare(English)\Chrome\Application\chrome.exe"

    # 2. 核心去安全配置 (防止弹窗和拦截)
    prefs = {
        "profile.default_content_settings.popups": 0,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": False,
        "profile.password_manager_enabled": False
    }
    if download_dir:
        download_path = str(Path(download_dir).resolve())
        prefs["download.default_directory"] = download_path
        prefs["directory_upgrade"] = True
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument('--ignore-certificate-errors')
    
    # 3. 显示模式
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
    else:
        opts.add_argument("--start-maximized")

    # 4. 启动驱动
    # 自动定位与本文件同级的 chromedriver.exe，避免依赖工作目录
    driver_path = Path(__file__).resolve().parent / "chromedriver.exe"
    try:
        service = Service(executable_path=str(driver_path))
        return webdriver.Chrome(service=service, options=opts)
    except Exception as e:
        print(f"[Browser] 启动失败，请检查 chromedriver 路径: {e}")
        raise e
