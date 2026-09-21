import argparse
import os
import sys
import time
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime, timedelta
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from xxt.browser import create_driver
from xxt.grader import (
    InternalAuth,
    enter_course_robust,
    matches_target_value,
    recursive_find_element,
)


def list_zip_files(directory: Path):
    return {str(p.resolve()) for p in Path(directory).glob("*.zip")}


def wait_for_new_zip_with_rescue(driver, directory: Path, before_set, timeout=300):
    start = time.time()
    print("[下载] 开始监控下载文件夹...")
    while time.time() - start < timeout:
        for p in Path(directory).glob("*.zip"):
            full = str(p.resolve())
            if full not in before_set and p.suffix != ".crdownload" and p.stat().st_size > 0:
                return full
        try:
            current_url = driver.current_url
            if "fanyadata" in current_url or ".zip" in current_url:
                print("[下载] 浏览器卡在下载链接页，尝试刷新...")
                driver.refresh()
                time.sleep(5)
        except:
            pass
        time.sleep(1)
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
        if not dropdown:
            return ["当前班级"]
        driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(1)
        titles = []
        for opt in driver.find_elements(By.CSS_SELECTOR, "li.classli"):
            title = opt.get_attribute("title") or opt.text
            if title:
                titles.append(title.strip())
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
        if not dropdown:
            return False
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
    V7 批量收割版：
    1. 不锁定特定 ID，而是锁定【时间窗口】。
    2. 只要是“当前时间”附近的最新任务，全部加入监控队列。
    3. 支持“导出所有班级”产生的多个文件，直到全部下载完毕才退出。
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    existing_zips = list_zip_files(download_dir)
    
    print("[下载] 正在寻找导出入口...")
    
    # ================= 1. 触发导出 (保持原样) =================
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
        try: export_btn = driver.find_element(By.CSS_SELECTOR, "a.exportExamAttachment")
        except: 
            try: export_btn = driver.find_element(By.XPATH, "//a[contains(text(),'导出考试附件')]")
            except: pass

    if not export_btn:
        print("[❌ 错误] 找不到导出按钮")
        return False

    driver.execute_script("arguments[0].click();", export_btn)
    print("[下载] 已触发导出弹窗")
    time.sleep(2) 

    # ================= 2. 暴力选择选项 (保持原样) =================
    def brute_force_click(target_text):
        try:
            xpath = f"//*[contains(text(), '{target_text}')]"
            text_el = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].click();", text_el)
            try: driver.execute_script("arguments[0].previousElementSibling.click();", text_el)
            except: pass
            try: driver.execute_script("arguments[0].parentNode.click();", text_el)
            except: pass
            return True
        except: return False

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

    # ================= 3. 进入下载中心 (V7 核心逻辑) =================
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "downloadcenter")))
    except:
        print("[❌ 错误] 无法进入下载中心")
        return False

    print("="*50)
    print("[下载中心] 🚀 启动批量收割模式 (监控最近5分钟的任务)")
    print("="*50)

    refresh_btn_selector = "a.refreshBtn"
    downloaded_tasks = set() # 已下载的任务名
    
    # 记录脚本进入下载中心的时间
    start_watch_time = datetime.now()
    
    # 辅助：判断是否是“新”任务 (时间误差 10 分钟内)
    def is_fresh_task(time_str):
        try:
            # 格式: 01-10 14:36
            now = datetime.now()
            task_time = datetime.strptime(f"{now.year}-{time_str}", "%Y-%m-%d %H:%M")
            # 计算时间差
            delta = abs((now - task_time).total_seconds())
            return delta < 600 # 600秒 = 10分钟内都算
        except:
            return False

    # 循环监控
    max_loops = 240 # 20分钟
    
    for loop in range(max_loops):
        try:
            # 每次重新抓取前 15 行 (防止被挤下去)
            rows = driver.find_elements(By.CSS_SELECTOR, "#downloadContent ul.dataBody_td")
            
            # 这一轮发现了多少个【正在进行】或【刚完成】的新任务
            active_fresh_tasks = 0
            
            for index, row in enumerate(rows):
                if index > 15: break 
                
                try:
                    # 提取信息
                    t_name = row.find_element(By.CSS_SELECTOR, "li:nth-child(1)").text.strip()
                    t_time = row.find_element(By.CSS_SELECTOR, "li:nth-child(2)").text.strip()
                    t_status = row.find_element(By.CSS_SELECTOR, "li:nth-child(3)").text.strip()
                    
                    # 🔥 核心判断：只关心时间匹配的新任务
                    if not is_fresh_task(t_time):
                        continue
                        
                    # 这是一个新任务！
                    if t_name in downloaded_tasks:
                        # 已经下载过了，忽略
                        continue
                        
                    # 只要是新任务，不管是在“导出中”还是“成功”，都算 Active
                    active_fresh_tasks += 1
                    
                    print(f"   🔎 发现新任务: {t_name} | {t_status}")

                    if "导出成功" in t_status:
                        print(f"      ✅ 准备下载...")
                        dl_link = row.find_element(By.CSS_SELECTOR, "li:nth-child(4) a")
                        driver.execute_script("arguments[0].setAttribute('download', '');", dl_link)
                        driver.execute_script("arguments[0].click();", dl_link)
                        
                        # 标记为已完成
                        downloaded_tasks.add(t_name)
                        active_fresh_tasks -= 1 # 处理完了，计数减1
                        
                    elif "导出失败" in t_status:
                        print(f"      ❌ 导出失败")
                        downloaded_tasks.add(t_name) # 标记为处理过
                        active_fresh_tasks -= 1
                    
                    elif "导出中" in t_status or "排队" in t_status:
                        print(f"      ⏳ 等待打包...")
                
                except Exception as e:
                    continue

            # ---------------- 退出策略 ----------------
            # 1. 如果我们已经下载了至少 1 个文件
            # 2. 并且当前列表里没有“正在跑”的新任务了
            if len(downloaded_tasks) > 0 and active_fresh_tasks == 0:
                print("="*50)
                print(f"[下载中心] 🎉 批量任务全部完成！共下载: {len(downloaded_tasks)} 个文件")
                print("="*50)
                break
            
            # 如果跑了 5 轮还没发现任何新任务，可能是还没刷出来，继续等
            if len(downloaded_tasks) == 0 and active_fresh_tasks == 0:
                print(f"[下载中心] 暂未扫描到新任务，等待后台生成... (已等待 {loop*5}s)")
            
            # 刷新页面
            driver.find_element(By.CSS_SELECTOR, refresh_btn_selector).click()
            time.sleep(5)

        except Exception as e:
            print(f"[异常] {e}")
            time.sleep(5)
            try: driver.find_element(By.CSS_SELECTOR, refresh_btn_selector).click()
            except: pass

    # ================= 4. 等待文件落地 =================
    print("[下载] 等待文件写入磁盘...")
    # 针对批量下载，多给点时间
    wait_for_new_zip_with_rescue(driver, download_dir, existing_zips, timeout=600)
    
    # 重新检查文件
    final_zips = list_zip_files(download_dir)
    new_files = final_zips - existing_zips
    
    if new_files:
        print(f"[下载] ✅ 成功捕获 {len(new_files)} 个文件")
        return True
    else:
        # 只要流程走完了，我们认为成功 (因为可能文件被之前下载过了)
        return True

def download_exam_for_class(driver, exam_name, download_dir: Path, main_window):
    """
    智能下载逻辑 V3：
    1. 【新增】捷径检测：如果当前已经在批阅页面（能看到'更多'或'导出'），直接开始下载，跳过繁琐的查找步骤。
    2. 常规回退：如果不在批阅页面，才去考试列表里搜索。
    """
    ensure_exam_frames(driver)
    
    # ================= 🔥 捷径检测 (Fast Track) =================
    print("[导航] 正在检查是否已在批阅页面...")
    try:
        # 尝试直接寻找“更多”按钮或者“导出”按钮
        # 只要找到其中一个，说明我们就在那个“不用动脑子直接点”的页面
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'更多')] | //a[contains(text(),'更多')] | //a[contains(text(),'导出考试附件')]"))
        )
        print("[导航] ⚡️ 触发捷径：检测到已在批阅页面，跳过考试搜索，直接下载！")
        
        # 直接调用下载逻辑
        return perform_download(driver, download_dir)
        
    except:
        print("[导航] 未检测到批阅按钮，进入常规搜索模式...")
        # 没找到快捷按钮，说明可能是第一次进，或者页面刷新回去了，继续下面的常规流程
        pass

    # ================= 下面是之前的常规逻辑 (只有第一次或出错时才会跑到这) =================
    
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
        # 这是一个很具体的定位，结合 考试名 和 按钮名
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

def process_all_classes(driver, exam_name, download_dir: Path):
    click_sidebar(driver, exam_name)
    class_titles = collect_class_titles(driver)
    print(f"[班级] 待检查: {class_titles}")

    main_window = driver.current_window_handle
    results = {}
    for cls in class_titles:
        print(f"[班级] 切换到: {cls}")
        if not select_class(driver, cls):
            print(f"[班级] 选择失败: {cls}")
            results[cls] = False
            continue
        success = download_exam_for_class(driver, exam_name, download_dir, main_window)
        results[cls] = success
    return results


def main():
    parser = argparse.ArgumentParser(description="Multi-class download test for Chaoxing exams/homework.")
    parser.add_argument("--course", required=True, help="Course name to open")
    parser.add_argument("--exam", required=True, help="Exam/assignment name to locate")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--keep-visible", action="store_true", help="Keep browser visible (do not hide after login)")
    parser.add_argument("--download-dir", help="Download directory", default=str(CURRENT_DIR / "downloads"))
    args = parser.parse_args()

    download_dir = Path(args.download_dir).resolve()
    driver = create_driver(headless=args.headless, download_dir=str(download_dir))
    auth = InternalAuth(driver, hide_window=not args.keep_visible)

    try:
        if not auth.login():
            print("Login failed.")
            return

        if not enter_course_robust(driver, args.course):
            print(f"Course not found: {args.course}")
            return

        results = process_all_classes(driver, args.exam, download_dir)
        print(f"[汇总] 下载结果: {results}")
    finally:
        print("Closing browser in 15 seconds...")
        time.sleep(15)
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
