import time
print("[MAIN.PY] 脚本已启动！")
import os
import argparse
import json
from pathlib import Path
import sys
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import platform # 记得在文件最开头引入这个，或者这里直接用
import difflib # 🟢 新增这个库

# ================= 配置部分 =================
def get_config_value(value, env_key, default):
    return value if value not in (None, "") else os.environ.get(env_key, default)

parser = argparse.ArgumentParser()
parser.add_argument("--course", help="课程名称")
parser.add_argument("--sidebar", help="侧边栏按钮名称", default="考试")
parser.add_argument("--exam", help="目标作业/考试名称")
parser.add_argument("--exam-button", help="批阅按钮文本", default="批阅")
parser.add_argument("--download-dir", help="下载目录")
parser.add_argument("--login-url", help="登录URL")
parser.add_argument("--course-url", help="课程列表URL")
parser.add_argument("--chromedriver", help="Chromedriver 路径")
parser.add_argument("--backend-url", help="后端基地址")
parser.add_argument("--backend-token", help="后端 Token")
parser.add_argument("--state-file", help="状态文件路径")
parser.add_argument("--list-courses", action="store_true")
parser.add_argument("--list-exams", action="store_true")
parser.add_argument("--classes", help="仅处理指定班级，逗号分隔")
args = parser.parse_args()

BACKEND_BASE_URL = get_config_value(args.backend_url, "BACKEND_URL", "http://127.0.0.1:5000").rstrip("/")
BACKEND_TOKEN = get_config_value(args.backend_token, "BACKEND_TOKEN", None)
TARGET_COURSE_NAME = get_config_value(args.course, "TARGET_COURSE_NAME", "信息检索")
TARGET_EXAM_NAME = get_config_value(args.exam, "TARGET_EXAM_NAME", "期末结课论文")
TARGET_SIDEBAR_BUTTON = get_config_value(args.sidebar, "TARGET_SIDEBAR_BUTTON", "考试")
TARGET_EXAM_BUTTON_TEXT = get_config_value(args.exam_button, "TARGET_EXAM_BUTTON_TEXT", "批阅")

# 路径配置
LOGIN_URL = 'https://passport2.chaoxing.com/login?fid=&newversion=true&refer=https%3A%2F%2Fi.chaoxing.com'
COURSE_URL = 'https://i.chaoxing.com/base?t=1762685225957'
DRIVER_PATH = get_config_value(args.chromedriver, "XXT_CHROMEDRIVER", 'chromedriver.exe')
DOWNLOAD_DIR = os.path.abspath(get_config_value(args.download_dir, "XXT_DOWNLOAD_DIR", os.path.join(os.getcwd(), "downloads")))
STATE_FILE = os.path.abspath(get_config_value(args.state_file, "XXT_STATE_FILE", os.path.join(os.getcwd(), "runner_state.json")))
# 🟢 修复：统一 Cookie 文件路径，与回填流程保持一致
# 计算 backend 目录路径（main.py 在 xuexitong/cstudy/，需要向上两级到项目根，再进入 backend）
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(os.path.dirname(os.path.dirname(current_file_dir)), "backend")
COOKIE_FILE = os.path.join(backend_dir, "xxt_cookies.json")
SHOULD_DELAY_CLOSE = not (args.list_courses or args.list_exams)

if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

# ================= 辅助函数 =================
def write_state(stage, message=None, **extra):
    payload = {"stage": stage, "message": message, "timestamp": time.time(), "jobId": extra.get('jobId')}
    payload.update(extra)
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
    except: pass

def list_zip_files(directory):
    return {str(p.resolve()) for p in Path(directory).glob("*.zip")}

def wait_for_new_zip_with_rescue(driver, directory, before_set, timeout=300):
    start = time.time()
    print(f"[V54] 开始监控下载文件夹...")
    
    while time.time() - start < timeout:
        # 1. 检查文件是否出现
        for p in Path(directory).glob("*.zip"):
            full = str(p.resolve())
            if full not in before_set and p.suffix != ".crdownload" and p.stat().st_size > 0:
                return full
        
        # 2. 救急逻辑：检查是否卡在下载链接页
        try:
            current_url = driver.current_url
            if "fanyadata" in current_url or ".zip" in current_url:
                print(f"[V54] 🚑 浏览器卡在下载链接页，尝试刷新...")
                driver.refresh()
                time.sleep(5)
        except:
            pass

        time.sleep(1)
    return None

def save_cookies(driver):
    try:
        with open(COOKIE_FILE, 'w') as f: json.dump(driver.get_cookies(), f)
    except: pass

def load_cookies(driver):
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r') as f: cookies = json.load(f)
            driver.get(LOGIN_URL)
            for c in cookies: 
                if 'expiry' in c: del c['expiry']
                driver.add_cookie(c)
            return True
        except: pass
    return False

def download_via_requests(driver, url, filename, download_dir):
    """
    使用 requests 接管下载，显示进度条，提升大文件下载稳定性。
    """
    import sys  # 确保导入 sys
    print(f"[高速下载]  正在接管下载: {filename}")
    print(f"            链接: {url[:50]}...")
    
    # 1. 偷取浏览器的 Cookies
    selenium_cookies = driver.get_cookies()
    session = requests.Session()
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    
    # 2. 伪造 User-Agent
    user_agent = driver.execute_script("return navigator.userAgent;")
    headers = {"User-Agent": user_agent}
    
    # 3. 流式下载
    local_path = os.path.join(download_dir, filename)
    try:
        with session.get(url, headers=headers, stream=True, timeout=120) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            with open(local_path, 'wb') as f:
                if total_size == 0:
                    print("   [未知大小] 正在写入...")
                    f.write(r.content)
                else:
                    downloaded = 0
                    chunk_size = 1024 * 1024 # 1MB per chunk
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 简易进度条
                            percent = int(downloaded / total_size * 100)
                            sys.stdout.write(f"\r   ⬇️  下载进度: {percent}% [{downloaded//1024//1024}MB / {total_size//1024//1024}MB]")
                            sys.stdout.flush()
        print("\n   ✅ 下载完成！")
        return local_path
    except Exception as e:
        print(f"\n   ❌ 下载失败: {e}")
        return None

def matches_target_value(target, label, identifier):
    """
    智能模糊匹配：
    1. 精确匹配
    2. 包含匹配 (去除口语后缀)
    3. 相似度匹配 (防止少字/多字)
    """
    if not target: return False
    if identifier and target == identifier: return True
    
    # 统一转小写并去空格
    t = target.lower().strip()
    l = label.lower().strip()
    
    # 🟢 1. 绝对包含匹配 (最准)
    # 只要 A 包含 B，或者 B 包含 A
    if t in l or l in t:
        return True
    
    # 🟢 2. 去除口语后缀再试 (针对 "智能合约课" vs "智能合约")
    suffixes = ["课", "课程", "班", "教学班", "（", "("] # 遇到括号也截断
    t_clean = t
    for suffix in suffixes:
        if suffix in t_clean:
            t_clean = t_clean.split(suffix)[0] # 截断后缀
            
    if t_clean and len(t_clean) > 1: 
        if t_clean in l or l in t_clean:
            return True

    # 🟢 3. 相似度匹配 (最后的救命稻草)
    # 计算两个字符串的相似度，如果超过 60% 像，就认为是同一个
    # 比如 "智能合药" (错别字) vs "智能合约"
    similarity = difflib.SequenceMatcher(None, t, l).ratio()
    if similarity > 0.6: 
        print(f"[智能匹配] '{t}' ≈ '{l}' (相似度: {similarity:.2f}) -> 匹配成功")
        return True
            
    return False

def resolve_target_label(target, candidates):
    if not target: return target
    for item in candidates:
        if item.get("id") == target: return item.get("name") or target
    return target

def upload_zip_to_backend(file_path):
    if not BACKEND_TOKEN: return None
    try:
        with open(file_path, "rb") as fh:
            files = {"file": (os.path.basename(file_path), fh, "application/zip")}
            res = requests.post(f"{BACKEND_BASE_URL}/api/upload/jobs", headers={"Authorization": f"Bearer {BACKEND_TOKEN}"}, files=files)
        return res.json()
    except Exception as e:
        print(f"[上传失败] {e}")
        return None

# ================= 下载与导航增强 =================
def recursive_find_element(driver, locator):
    """递归查找元素（应对多层 iframe）"""
    try:
        if len(driver.find_elements(*locator)) > 0:
            return driver.find_element(*locator)
    except:
        pass
    
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in iframes:
        try:
            driver.switch_to.frame(frame)
            found = recursive_find_element(driver, locator)
            if found: 
                return found
            driver.switch_to.parent_frame()
        except:
            driver.switch_to.parent_frame()
    return None

def ensure_exam_frames(driver):
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
    except:
        driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
    except:
        pass

def collect_class_titles(driver):
    try:
        driver.switch_to.default_content()
        dropdown = recursive_find_element(driver, (By.CSS_SELECTOR, "a.banji_select_name"))
        driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(1)
        titles = []
        for opt in driver.find_elements(By.CSS_SELECTOR, "li.classli"):
            title = opt.get_attribute("title") or opt.text
            if title:
                titles.append(title.strip())
        # 去重保持顺序
        titles_unique = []
        for t in titles:
            if t not in titles_unique:
                titles_unique.append(t)
        try:
            driver.execute_script("arguments[0].click();", dropdown)
        except:
            pass
        return titles_unique or ["当前班级"]
    except:
        return ["当前班级"]

def select_class(driver, title):
    try:
        driver.switch_to.default_content()
        dropdown = recursive_find_element(driver, (By.CSS_SELECTOR, "a.banji_select_name"))
        driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(0.5)
        xpath = f"//li[@title='{title}'] | //li[normalize-space(text())='{title}']"
        opt = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(1.5)
        return True
    except:
        return False

def click_sidebar(driver, exam_name):
    prefer_assignment = "作业" in exam_name
    sidebar_order = ["作业", "考试"] if prefer_assignment else ["考试", "作业"]
    for sidebar_label in sidebar_order:
        driver.switch_to.default_content()
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, f"//a[@title='{sidebar_label}']"))
            )
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            print(f"[导航] 点击侧边栏 [{sidebar_label}] 成功")
            return True
        except:
            continue
    print("[导航] 侧边栏未点击成功，继续尝试列表")
    return True

def perform_download(driver, download_dir: Path):
    """
    批量收割：支持“导出考试下所有班级”产生的多个任务，轮询下载中心直到全部完成。
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    existing_zips = list_zip_files(download_dir)

    print("[下载] 正在寻找导出入口...")
    export_btn = None
    try:
        more_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'更多')] | //a[contains(text(),'更多')]"))
        )
        driver.execute_script("arguments[0].click();", more_btn)
        export_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'导出考试附件')]"))
        )
    except:
        try:
            export_btn = driver.find_element(By.CSS_SELECTOR, "a.exportExamAttachment")
        except:
            try:
                export_btn = driver.find_element(By.XPATH, "//a[contains(text(),'导出考试附件')]")
            except:
                pass

    if not export_btn:
        print("[❌ 错误] 找不到导出按钮")
        return False

    driver.execute_script("arguments[0].click();", export_btn)
    print("[下载] 已触发导出弹窗")
    time.sleep(2)

    def brute_force_click(target_text):
        try:
            xpath = f"//*[contains(text(), '{target_text}')]"
            text_el = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", text_el)
            try:
                driver.execute_script("arguments[0].previousElementSibling.click();", text_el)
            except:
                pass
            try:
                driver.execute_script("arguments[0].parentNode.click();", text_el)
            except:
                pass
            return True
        except:
            return False

    brute_force_click("导出考试下所有班级")
    time.sleep(0.5)
    brute_force_click("导出提交附件")
    time.sleep(0.5)

    try:
        confirm_btn = driver.find_element(By.CSS_SELECTOR, "a.confirmDown")
        driver.execute_script("arguments[0].click();", confirm_btn)
        print("[下载] 已点击确认，任务已推送到后台...")
    except:
        try:
            confirm_btn = driver.find_element(By.XPATH, "//a[contains(text(),'确定')] | //span[contains(text(),'确定')]")
            driver.execute_script("arguments[0].click();", confirm_btn)
        except:
            print("[❌ 错误] 找不到确定按钮")
            return False

    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "downloadcenter")))
    except:
        print("[❌ 错误] 无法进入下载中心")
        return False

    print("=" * 50)
    print("[下载中心] 🚀 启动批量收割模式 (监控最近10分钟的任务)")
    print("=" * 50)

    refresh_btn_selector = "a.refreshBtn"
    downloaded_tasks = set()

    def is_fresh_task(time_str):
        try:
            now = datetime.now()
            task_time = datetime.strptime(f"{now.year}-{time_str}", "%Y-%m-%d %H:%M")
            return abs((now - task_time).total_seconds()) < 600
        except:
            return False

    max_loops = 240  # 约20分钟
    for loop in range(max_loops):
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "#downloadContent ul.dataBody_td")
            active_fresh_tasks = 0
            for index, row in enumerate(rows):
                if index > 15:
                    break
                try:
                    t_name = row.find_element(By.CSS_SELECTOR, "li:nth-child(1)").text.strip()
                    t_time = row.find_element(By.CSS_SELECTOR, "li:nth-child(2)").text.strip()
                    t_status = row.find_element(By.CSS_SELECTOR, "li:nth-child(3)").text.strip()

                    if not is_fresh_task(t_time):
                        continue
                    if t_name in downloaded_tasks:
                        continue

                    active_fresh_tasks += 1
                    print(f"   🔎 发现新任务: {t_name} | {t_status}")

                    if "导出成功" in t_status:
                        print(f"      ✅ 任务已就绪，准备接管下载...")
                        
                        try:
                            # 1. 获取下载链接 (href) 而不是点击
                            dl_link_el = row.find_element(By.CSS_SELECTOR, "li:nth-child(4) a")
                            download_url = dl_link_el.get_attribute("href")
                            
                            # 2. 构造文件名 (为了防止乱码，尽量用任务名+后缀)
                            safe_name = t_name.replace(" ", "_").replace("/", "_") 
                            if not safe_name.endswith(".zip"):
                                safe_name += ".zip"
                                
                            # 3. 调用高速下载
                            if download_url and "http" in download_url:
                                saved_path = download_via_requests(driver, download_url, safe_name, download_dir)
                                if saved_path:
                                    downloaded_tasks.add(t_name)
                                    active_fresh_tasks -= 1  # 处理完了
                                else:
                                    print("      ❌ requests 下载失败，尝试回退到浏览器点击...")
                                    raise Exception("Requests failed")
                            else:
                                raise Exception("Empty URL")

                        except Exception as dl_err:
                            # 备用方案：如果 requests 失败了，还是用老办法点一下
                            print(f"      ⚠️ 接管失败 ({dl_err})，回退到浏览器默认下载...")
                            try:
                                driver.execute_script("arguments[0].click();", dl_link_el)
                                downloaded_tasks.add(t_name)
                                active_fresh_tasks -= 1
                            except:
                                pass
                    elif "导出失败" in t_status:
                        print("      ❌ 导出失败")
                        downloaded_tasks.add(t_name)
                        active_fresh_tasks -= 1
                    elif "导出中" in t_status or "排队" in t_status:
                        print("      ⏳ 等待打包...")
                except:
                    continue

            if len(downloaded_tasks) > 0 and active_fresh_tasks == 0:
                print("=" * 50)
                print(f"[下载中心] 🎉 批量任务全部完成！共下载: {len(downloaded_tasks)} 个文件")
                print("=" * 50)
                break

            if len(downloaded_tasks) == 0 and active_fresh_tasks == 0:
                print(f"[下载中心] 暂未扫描到新任务，等待后台生成... (已等待 {loop * 5}s)")

            driver.find_element(By.CSS_SELECTOR, refresh_btn_selector).click()
            time.sleep(5)
        except Exception as e:
            print(f"[异常] {e}")
            time.sleep(5)
            try:
                driver.find_element(By.CSS_SELECTOR, refresh_btn_selector).click()
            except:
                pass

    print("[下载] 等待文件写入磁盘...")
    wait_for_new_zip_with_rescue(driver, download_dir, existing_zips, timeout=600)
    final_zips = list_zip_files(download_dir)
    new_files = final_zips - existing_zips
    if new_files:
        print(f"[下载] ✅ 成功捕获 {len(new_files)} 个文件")
        return True
    else:
        return True

def download_exam_for_class(driver, exam_name, download_dir: Path, main_window):
    """
    优先检测是否已在批阅页，直接下载；否则从列表进入批阅再下载。
    """
    ensure_exam_frames(driver)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'更多')] | //a[contains(text(),'更多')] | //a[contains(text(),'导出考试附件')]"))
        )
        print("[导航] ⚡️ 已在批阅页面，直接下载")
        write_state("downloading", f"检测到批阅页，准备导出 {exam_name}")
        return perform_download(driver, download_dir)
    except:
        pass

    headers = driver.find_elements(By.CSS_SELECTOR, "h2.list_li_tit")
    header_texts = [h.text.strip() for h in headers]
    if not header_texts:
        print("   (本班无考试列表，跳过)")
        return False

    target_title = None
    for title in header_texts:
        if matches_target_value(exam_name, title, None):
            target_title = title
            break

    if not target_title:
        print("   (本班未找到目标考试，跳过)")
        return False

    action_texts = ["批阅", "批改", "评阅"]
    for action in action_texts:
        target_xpath = f"//li[.//h2[contains(text(), '{target_title}')]]//a[contains(text(), '{action}')]"
        try:
            btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.XPATH, target_xpath)))
            old_handles = driver.window_handles
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)

            new_handle = None
            try:
                WebDriverWait(driver, 4).until(EC.new_window_is_opened(old_handles))
                new_handles = driver.window_handles
                new_handle = [h for h in new_handles if h not in old_handles][0]
                driver.switch_to.window(new_handle)
                print("[导航] 检测到新窗口，已切换")
            except:
                print("[导航] 未检测到新窗口，假定在当前 Frame 继续")
                pass

            write_state("downloading", f"已打开批阅页面，准备导出 {exam_name}")

            success = perform_download(driver, download_dir)

            try:
                if new_handle and new_handle in driver.window_handles:
                    driver.close()
            except:
                pass
            if new_handle:
                driver.switch_to.window(main_window)
                ensure_exam_frames(driver)
            return success
        except:
            continue
    print("   (本班未找到目标考试，跳过)")
    return False

def process_all_classes(driver, exam_name, download_dir: Path, class_filter=None):
    """
    【硬闯模式】
    不区分单/多班级，不进行预判。
    逻辑：拿到列表 -> 挨个试着点 -> 无论点没点着下拉框，都去尝试找考试 -> 找到就下载。
    """
    # 0. 超速捷径：若当前已在批阅页，直接导出并上报状态
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'更多')] | //a[contains(text(),'导出考试附件')] | //a[contains(text(),'批量导出考试附件')]"))
        )
        print("[捷径] 当前已在批阅页，直接导出所有班级")
        write_state("downloading", f"检测到批阅页，准备导出 {exam_name}")
        success = perform_download(driver, download_dir)
        return {"FastTrack": success}
    except:
        pass

    click_sidebar(driver, exam_name)
    
    # 获取列表（可能是["计科1班", "计科2班"]，也可能是["当前班级"]）
    class_titles = collect_class_titles(driver)
    
    # 过滤掉“全部班级”“默认班级”，并应用外部过滤（如有）
    filtered_classes = []
    for c in class_titles:
        if c in ("全部班级", "默认班级"):
            continue
        if class_filter and not any(matches_target_value(f, c, None) for f in class_filter):
            continue
        filtered_classes.append(c)
    if not filtered_classes:
        filtered_classes = class_titles  # 兜底：全空时使用原始列表
    class_titles = filtered_classes

    # 提前把班级列表写入状态，促使前端进入下一步
    write_state("select_exam_classes", f"发现班级: {class_titles}", classes=class_titles)
    
    print(f"[班级] 待扫描队列: {class_titles}")
    main_window = driver.current_window_handle
    results = {}

    for i, cls in enumerate(class_titles):
        print(f"[流程] 正在处理第 {i+1} 个入口: {cls}")
        
        # 1. 尝试切换班级 (Try Switch)
        # 我们不管它返回 True 还是 False。
        # 如果是多班级，它会切换成功；如果是单班级（没下拉框），它会失败。
        # 但！哪怕失败了，我们也要继续往下走！因为可能我们就已经在目标页面上了！
        select_class(driver, cls) 
        
        # 2. 直接找考试 (Just Find Exam)
        # 只要当前页面有考试，download_exam_for_class 就能搞定
        success = download_exam_for_class(driver, exam_name, download_dir, main_window)
        results[cls] = success
        
        # 3. 结果判定
        if success:
            print(f"✅ [成功] 在入口 [{cls}] 找到目标并完成批量导出！")
            print("   -> 触发熔断机制：已获取全部数据，停止扫描剩余班级。")
            break  # 成功一次，直接结束
        else:
            print(f"   -> 在当前视图未找到目标考试，尝试下一个...")

    return results
# ================= 主逻辑 =================
write_state("start", f"准备访问 {LOGIN_URL}")
driver = None

try:
    # --- 3. 浏览器配置 (V54: 核弹级去安全化) ---
    opts = Options()
    if platform.system() == 'Linux':
        print("[启动] 检测到 Linux 环境，使用服务器配置...")
        # 服务器上的 Chrome 安装路径 (刚才我们在黑窗口 apt install 的位置)
        opts.binary_location = "/usr/bin/google-chrome"
        # 服务器必须加这几个参数，否则跑不起来
        opts.add_argument("--no-sandbox") 
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--headless=new")
    else:
        print("[启动] 检测到 Windows 环境，使用本地配置...")
        # 你原来的本地路径
        opts.binary_location = r"D:\SoftWare(English)\Chrome\Application\chrome.exe"

   
    
    prefs = {
        "profile.default_content_settings.popups": 0,
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        # 🔥 核心修改：彻底关闭安全浏览功能
        "safebrowsing.enabled": False, 
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
        "download.extensions_to_open": "",
        "profile.password_manager_enabled": False,
        "browser.helperApps.neverAsk.saveToDisk": "application/zip,application/octet-stream"
    }
    opts.add_experimental_option("prefs", prefs)
    
    # 🔥 命令行参数：从启动层面禁用保护
    opts.add_argument('--safebrowsing-disable-download-protection')
    opts.add_argument('--safebrowsing-disable-extension-blacklist')
    opts.add_argument('--disable-client-side-phishing-detection')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--ignore-certificate-errors')

    # 优先根据环境决定是否启用无头模式：
    # - XXT_HEADLESS=1/true/yes 强制无头（适合没有图形界面的服务器）
    # - 没有 DISPLAY 变量（常见于 Linux 服务器）也自动无头
    # - 否则，如果存在 cookie 则默认无头，避免弹窗打扰
    force_headless_env = os.getenv("XXT_HEADLESS", "").lower() in ("1", "true", "yes")
    no_display = not os.getenv("DISPLAY")
    is_headless = False

    if force_headless_env or no_display:
        print("[启动] 检测到服务器环境，强制开启【无头模式】...")
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        is_headless = True
    elif os.path.exists(COOKIE_FILE):
        print("[启动] 尝试【无头/隐身模式】...")
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        is_headless = True
    else:
        print("[启动] 启动【可见模式】...")

    service = webdriver.chrome.service.Service(executable_path=DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=opts)

    # --- 4. 登录 ---
    load_cookies(driver)
    driver.get(COURSE_URL)
    time.sleep(2)

    if "passport2.chaoxing.com" in driver.current_url:
        print("[状态] 进入扫码登录流程...")
        
        # 1. 等待二维码元素加载 (根据您提供的HTML，ID是 quickCode)
        try:
            qr_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "quickCode"))
            )
            print("找到二维码元素，准备截图...")
            
            # 2. 定义二维码保存路径 (和 runner_state.json 同级)
            qr_filename = "login_qr.png"
            qr_path = os.path.join(os.path.dirname(STATE_FILE), qr_filename)
            
            # 3. 循环刷新截图 (防止二维码过期)
            # 我们在一个循环里等待登录，同时更新二维码图片
            start_login_wait = time.time()
            while time.time() - start_login_wait < 300: # 等待5分钟
                # 检查是否跳转成功
                if "passport2.chaoxing.com" not in driver.current_url:
                    print("登录成功！")
                    break
                try:
                    
                    # 只有当它 style="display: block;" 时，is_displayed() 才会返回 True
                    expire_overlay = driver.find_element(By.CSS_SELECTOR, ".ewmDisable")
                    
                    if expire_overlay.is_displayed():
                        print("[状态] ⚠️ 检测到二维码已失效，正在自动点击刷新...")
                        
                        # 2. 找到里面的“重新获取”按钮
                        refresh_btn = expire_overlay.find_element(By.TAG_NAME, "a")
                        
                        # 3. 点击刷新 (使用 JS 点击最稳，因为它可能被其他层遮挡)
                        driver.execute_script("arguments[0].click();", refresh_btn)
                        
                        # 4. 关键：等待新二维码加载出来，不然截图还是旧的
                        time.sleep(3) 
                        print("[状态] ✅ 已刷新二维码")
                except Exception as e:
                    pass # 没找到按钮就算了，继续截图
                
                # 截图保存 (覆盖旧图)
                try:
                    # 重新获取元素防止 stale element reference
                    qr_element = driver.find_element(By.ID, "quickCode")
                    qr_element.screenshot(qr_path)
                    
                    # 告诉前端：现在是 waiting_login 状态，且有图片 qrImage
                    write_state("waiting_login", "请扫描二维码登录", qrImage=qr_filename)
                except Exception as shot_err:
                    print(f"截图微小错误(不影响): {shot_err}")

                time.sleep(2) # 每2秒刷新一次状态
                
        except TimeoutException:
            print("未找到二维码元素！")
            write_state("error", "未找到登录二维码，请检查网络")
            raise

        # 登录成功后的处理
        print("正在隐藏窗口...")
        try:
            driver.minimize_window() # 尝试最小化
            driver.set_window_position(-3000, 0) # 移到屏幕左侧很远的地方
        except:pass
        time.sleep(2)
        save_cookies(driver)   
        driver.get(COURSE_URL)
    else:
        print("Cookie 登录成功！")
        save_cookies(driver)
        write_state("login_success")

    driver.get(COURSE_URL)

    # --- 6. 课程列表 ---
    print("加载课程...")
    for i in range(3):
        try:
            driver.switch_to.default_content()
            btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@name='新版课程']")))
            driver.execute_script("arguments[0].click();", btn)
            WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span.course-name')))
            break
        except:
            driver.refresh()
            time.sleep(3)

    # --- 9. 查找课程 ---
    print(f"查找课程: {TARGET_COURSE_NAME}")
    write_state("select_course", f"查找 {TARGET_COURSE_NAME}")
    courses = driver.find_elements(By.CSS_SELECTOR, 'div.teachCourse')
    
    if args.list_courses:
        data = [{"name": c.find_element(By.CSS_SELECTOR, 'span.course-name').text, "id": ""} for c in courses]
        write_state("courses_loaded", courses=data)
        sys.exit(0)

    found = False
    original_window = driver.current_window_handle
    for c in courses:
        try:
            title_el = c.find_element(By.CSS_SELECTOR, 'span.course-name')
            #调试
            text = title_el.text
            print(f"[调试] 扫描到课程: [{text}] vs 目标: [{TARGET_COURSE_NAME}]")
            if matches_target_value(TARGET_COURSE_NAME, title_el.text, None):
                print(f"找到课程: {title_el.text}")
                title_el.click()
                found = True
                break
        except: continue
    
    if not found: raise Exception(f"未找到课程: {TARGET_COURSE_NAME}")

    # --- 10. 切换窗口 ---
    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
    driver.switch_to.window([w for w in driver.window_handles if w != original_window][0])

    # --- 多班级导出流程 ---
    # 每次运行创建独立批次目录，避免文件混乱
    batch_dir_name = f"{TARGET_EXAM_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    batch_dir = Path(DOWNLOAD_DIR) / batch_dir_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    before_zips = list_zip_files(batch_dir)

    # 列出考试模式（仅当前班级）
    if args.list_exams:
        click_sidebar(driver, TARGET_EXAM_NAME)
        ensure_exam_frames(driver)
        headers = driver.find_elements(By.CSS_SELECTOR, 'h2.list_li_tit')
        data = [{"name": h.text, "id": ""} for h in headers]
        write_state("exams_loaded", exams=data)
        sys.exit(0)

    results = process_all_classes(driver, TARGET_EXAM_NAME, batch_dir)

    after_zips = list_zip_files(batch_dir)
    new_files = list(after_zips - before_zips)

    print(f"[汇总] 下载结果: {results}")
    write_state("download_complete", message="全部班级下载完成", results=results, files=new_files, batchDir=str(batch_dir))

    batch_jobs = []
    last_job = None
    if new_files and BACKEND_TOKEN:
        for f in new_files:
            res = upload_zip_to_backend(f)
            if res and res.get("jobId"):
                job_id = res.get("jobId")
                last_job = job_id or last_job
                cls_name = os.path.basename(f).replace(".zip", "")
                batch_jobs.append({"name": cls_name, "jobId": job_id})

    all_job_ids = [item["jobId"] for item in batch_jobs]
    write_state(
        "completed",
        "全部完成",
        results=results,
        files=new_files,
        jobId=last_job,
        jobIds=all_job_ids,
        batchJobs=batch_jobs,
        batchDir=str(batch_dir),
    )
    print("[V54] 脚本任务完成。")

except Exception as e:
    write_state("error", str(e))
    print(f"[错误] {e}")
finally:
    if 'driver' in locals() and driver:
        if SHOULD_DELAY_CLOSE: 
            print("保留浏览器60秒...")
            time.sleep(60)
        else:
            time.sleep(1)
        driver.quit()
