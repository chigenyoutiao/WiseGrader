import sys
import os
import json
import time
import argparse
import difflib
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# 🔥 关键：把 backend 目录加入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # backend/
sys.path.append(parent_dir)

from xxt.browser import create_driver

# 🟢 新增：状态文件路径（与 app.py 保持一致）
# 尝试导入 config，如果失败则使用默认路径
try:
    import config
    STATE_FILE = config.XXT_STATE_FILE
except:
    # 如果导入失败，使用相对路径计算（grader.py 在 backend/xxt/，需要向上两级到项目根）
    STATE_FILE = Path(parent_dir).parent / 'xuexitong' / 'cstudy' / 'runner_state.json'
STATE_FILE = Path(STATE_FILE)
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

def write_fill_state(stage, message=None, current_student=None, current_index=0, total=0, **extra):
    """写入回填状态到状态文件"""
    # 🟢 修复：进度计算应该是已完成数/总数，而不是当前索引/总数
    # current_index 表示已完成的数量（已完成数量）
    completed = current_index if current_index <= total else total
    progress = round((completed / total * 100) if total > 0 else 0, 1)
    
    payload = {
        "stage": stage,
        "message": message,
        "timestamp": time.time(),
        "currentStudent": current_student,
        "currentIndex": completed,  # 🟢 修复：表示已完成的数量
        "total": total,
        "progress": progress,
    }
    payload.update(extra)
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[状态] 写入状态文件失败: {e}")

# ==========================================
# 🟢 1. 内置修复版 Auth
# ==========================================
class InternalAuth:
    def __init__(self, driver, hide_window=True):
        self.driver = driver
        self.hide_window = hide_window
        self.cookie_file = os.path.join(parent_dir, "xxt_cookies.json")

    def load_cookies(self):
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r') as f: 
                    cookies = json.load(f)
                self.driver.get('https://passport2.chaoxing.com/login')
                success = 0
                for c in cookies:
                    if 'expiry' in c: del c['expiry']
                    if 'sameSite' in c: del c['sameSite']
                    try:
                        self.driver.add_cookie(c)
                        success += 1
                    except:
                        if 'domain' in c: 
                            del c['domain']
                            try:
                                self.driver.add_cookie(c)
                                success += 1
                            except: pass
                print(f"   🍪 [内置Auth] 恢复 {success} 个 Cookie")
                return True
            except: pass
        return False

    def save_cookies(self):
        try:
            with open(self.cookie_file, 'w') as f:
                json.dump(self.driver.get_cookies(), f)
            print("   💾 Cookie 已更新并保存")
        except: pass

    def login(self):
        print("   🔑 [内置Auth] 检查登录状态...")
        if self.load_cookies():
            self.driver.get('https://i.chaoxing.com/base')
            time.sleep(2)
            if "passport2.chaoxing.com" not in self.driver.current_url:
                print("   ✅ 免密登录成功！")
                if self.hide_window:
                    try:
                        self.driver.minimize_window()
                        self.driver.set_window_position(-3000, 0)
                    except:
                        pass
                return True
        
        if "passport2.chaoxing.com" not in self.driver.current_url:
             self.driver.get('https://passport2.chaoxing.com/login')
        print("   📸 [交互] 请扫描二维码...")
        end = time.time() + 300 
        while time.time() < end:
            if "passport2.chaoxing.com" not in self.driver.current_url:
                print("   ✅ 扫码成功！")
                time.sleep(2)
                self.save_cookies()
                if self.hide_window:
                    try:
                        self.driver.minimize_window()
                        self.driver.set_window_position(-3000, 0)
                    except:
                        pass
                return True
            time.sleep(1)
        return False

# ==========================================
# 🟢 2. 核心逻辑移植 (源自 test_relay_grading.py)
# ==========================================

def recursive_find_element(driver, locator):
    """递归查找元素（应对多层 iframe）"""
    try:
        if len(driver.find_elements(*locator)) > 0:
            return driver.find_element(*locator)
    except: pass
    
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in iframes:
        try:
            driver.switch_to.frame(frame)
            found = recursive_find_element(driver, locator)
            if found: return found
            driver.switch_to.parent_frame()
        except:
            driver.switch_to.parent_frame()
    return None




def matches_target_value(target, label, identifier=None):
    if not target:
        return False
    if identifier and target == identifier:
        return True

    t = target.lower().strip()
    l = label.lower().strip()

    if t in l or l in t:
        return True

    suffixes = ["课", "课程", "班", "教学班", "（", "("]
    t_clean = t
    for suffix in suffixes:
        if suffix in t_clean:
            t_clean = t_clean.split(suffix)[0]

    if t_clean and len(t_clean) > 1:
        if t_clean in l or l in t_clean:
            return True

    similarity = difflib.SequenceMatcher(None, t, l).ratio()
    if similarity > 0.6:
        print(f"[智能匹配] '{t}' ≈ '{l}' (相似度: {similarity:.2f}) -> 匹配成功")
        return True

    return False


def enter_course_robust(driver, course_name):
    print(f"    正在进入课程: {course_name}")
    course_url = "https://i.chaoxing.com/base"
    driver.get(course_url)

    for _ in range(3):
        try:
            driver.switch_to.default_content()
            btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@name='新版课程'] | //span[contains(text(),'新版课程')]"))
            )
            driver.execute_script("arguments[0].click();", btn)
            WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.course-name")))
            break
        except:
            driver.refresh()
            time.sleep(3)

    courses = driver.find_elements(By.CSS_SELECTOR, "div.teachCourse")
    if not courses:
        print("   ❌ 未获取到课程列表")
        return False

    original_window = driver.current_window_handle
    found = False
    for c in courses:
        try:
            title_el = c.find_element(By.CSS_SELECTOR, "span.course-name")
            text = title_el.text
            print(f"[调试] 扫描到课程: [{text}] vs 目标: [{course_name}]")
            if matches_target_value(course_name, text, None):
                print(f"找到课程: {text}")
                title_el.click()
                found = True
                break
        except:
            continue

    if not found:
        print(f"   ❌ 未找到课程: {course_name}")
        return False

    try:
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        for h in driver.window_handles:
            if h != original_window:
                driver.switch_to.window(h)
                break
    except:
        pass

    return True

def enter_exam_robust(driver, exam_name, target_class_name=None):
    """
    🛠️ 仿照 main.py 的稳定逻辑：
    1) 优先点击侧边栏指定栏目
    2) 使用列表标题 h2.list_li_tit 匹配
    3) 失败时再退回宽容查找
    4) 🟢 新增：如果指定了 target_class_name，只在该班级中查找并进入
    """
    prefer_assignment = "作业" in exam_name
    sidebar_order = ["作业", "考试"] if prefer_assignment else ["考试", "作业"]

    for sidebar_label in sidebar_order:
        print(f"   🔍 [强力模式] 正在查找: {exam_name} (栏目: {sidebar_label})")

        driver.switch_to.default_content()
        sidebar_clicked = False
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, f"//a[@title='{sidebar_label}']"))
            )
            driver.execute_script("arguments[0].click();", btn)
            print(f"      ✅ 点击侧边栏 [{sidebar_label}] 成功")
            sidebar_clicked = True
            time.sleep(2)
        except:
            for text in [sidebar_label, "作业/考试"]:
                try:
                    xpath = f"//a[@title='{text}'] | //span[text()='{text}'] | //li[contains(@class,'nav-item')]//span[contains(text(),'{text}')]"
                    btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"      ✅ 点击侧边栏 [{text}] 成功")
                    sidebar_clicked = True
                    time.sleep(2)
                    break
                except:
                    pass

        if not sidebar_clicked:
            print("      ⚠️ 未点击到侧边栏，尝试直接查找...")

        def collect_class_titles():
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

        def select_class(title):
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

        def matches_target_class(class_name, target_name):
            """匹配班级名称，支持模糊匹配"""
            if not target_name:
                return True
            # 完全匹配
            if class_name == target_name:
                return True
            # 包含匹配
            if target_name in class_name or class_name in target_name:
                return True
            # 使用相似度匹配（处理可能的差异，如"班级1" vs "班级1-期末考试"）
            similarity = difflib.SequenceMatcher(None, class_name, target_name).ratio()
            return similarity > 0.7

        class_titles = collect_class_titles()
        print(f"      📦 待检查班级列表: {class_titles}")
        
        # 🟢 新增：如果指定了目标班级，只处理匹配的班级
        if target_class_name:
            print(f"      🎯 目标班级: {target_class_name}")
            matched_classes = [cls for cls in class_titles if matches_target_class(cls, target_class_name)]
            if not matched_classes:
                print(f"      ❌ 未找到匹配的班级: {target_class_name}")
                print(f"      可用班级: {class_titles}")
                return False  # 找不到匹配的班级，直接返回失败
            class_titles = matched_classes
            print(f"      ✅ 找到匹配的班级: {class_titles}")

        for cls in class_titles:
            print(f"      🔄 检查班级: {cls}")
            # 始终显式选择当前班级，确保下拉有实际切换
            if not select_class(cls):
                print(f"         ⚠️ 选择班级失败: {cls}")

            driver.switch_to.default_content()
            try:
                try:
                    WebDriverWait(driver, 3).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
                    WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
                except:
                    driver.switch_to.default_content()
                    WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
            except:
                pass

            try:
                headers = driver.find_elements(By.CSS_SELECTOR, "h2.list_li_tit")
                for h in headers:
                    if matches_target_value(exam_name, h.text, None):
                        action_texts = ["批阅", "批改", "评阅"]
                        for action in action_texts:
                            target_xpath = f"//li[.//h2[contains(text(), '{h.text.strip()}')]]//a[contains(text(), '{action}')]"
                            try:
                                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, target_xpath)))
                                driver.execute_script("arguments[0].click();", btn)
                                print(f"      ✅ 点击 [{action}] 成功！班级: {cls}")
                                time.sleep(2)
                                # 🟢 如果指定了目标班级，找到后立即返回
                                if target_class_name:
                                    return True
                                # 否则继续查找所有班级（保留原逻辑）
                                return True
                            except:
                                pass
                # 兜底：宽容查找
                exam_xpath = f"//*[contains(text(), '{exam_name}')]"
                if len(driver.find_elements(By.XPATH, exam_xpath)) > 0:
                    print(f"      🎉 发现标题！正在寻找操作按钮...")
                    action_texts = ["批阅", "批改", "评阅"]
                    for action in action_texts:
                        btn_xpaths = [
                            f"//li[contains(., '{exam_name}')]//a[contains(text(), '{action}')]",
                            f"//tr[contains(., '{exam_name}')]//a[contains(text(), '{action}')]",
                            f"//div[contains(., '{exam_name}')]//a[contains(text(), '{action}')]"
                        ]
                        for bx in btn_xpaths:
                            try:
                                btn = driver.find_element(By.XPATH, bx)
                                driver.execute_script("arguments[0].click();", btn)
                                print(f"      ✅ 点击 [{action}] 成功！班级: {cls}")
                                time.sleep(2)
                                # 🟢 如果指定了目标班级，找到后立即返回
                                if target_class_name:
                                    return True
                                return True
                            except:
                                pass
            except:
                pass

    print("   ❌ 所有班级都找遍了，未找到该考试/作业。")
    return False

# ==========================================
# 🟢 3. 业务与填分逻辑
# ==========================================

def run_grading_task(course_name, exam_name, scores_file_path, target_class_name=None, student_info_file_path=None):
    print(f"🚀 [Grader] 启动回填任务...")
    if target_class_name:
        print(f"   📋 目标班级: {target_class_name}")
    
    # 🟢 新增：读取学生信息映射（学号 -> 姓名）
    student_info_map = {}
    if student_info_file_path and Path(student_info_file_path).exists():
        try:
            with open(student_info_file_path, 'r', encoding='utf-8') as f:
                student_info_map = json.load(f)
            print(f"   📋 已加载 {len(student_info_map)} 个学生信息")
        except Exception as e:
            print(f"   ⚠️ 读取学生信息文件失败: {e}")
    
    try:
        with open(scores_file_path, 'r', encoding='utf-8') as f:
            scores_data = json.load(f)
        scores_data = {str(k): v for k, v in scores_data.items()}
        total_students = len(scores_data)
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        write_fill_state("fill_score_error", f"读取分数文件失败: {e}", total=0)
        return

    # 🟢 初始化状态：开始回填
    write_fill_state("fill_score_running", "正在登录学习通...", total=total_students)

    driver = create_driver(headless=False) 
    auth = InternalAuth(driver)
    try:
        if not auth.login():
            write_fill_state("fill_score_error", "登录失败", total=total_students)
            return
        
        # 🟢 更新状态：登录成功，准备进入课程
        write_fill_state("fill_score_running", f"正在进入课程《{course_name}》...", total=total_students)
        
        # 进入课程
        if not enter_course_robust(driver, course_name): 
            print(f"❌ 找不到课程: {course_name}")
            write_fill_state("fill_score_error", f"找不到课程: {course_name}", total=total_students)
            return

        # 🟢 更新状态：课程已进入，准备进入考试
        class_text = f"（{target_class_name}）" if target_class_name else ""
        write_fill_state("fill_score_running", f"正在进入考试《{exam_name}》{class_text}...", total=total_students)

        # 🟢 修改：使用移植后的强力导航，并传入目标班级名称
        if not enter_exam_robust(driver, exam_name, target_class_name):
            write_fill_state("fill_score_error", f"找不到考试: {exam_name}", total=total_students)
            return

        # 🟢 更新状态：考试已进入，开始回填
        write_fill_state("fill_score_running", "开始回填学生成绩...", current_index=0, total=total_students)
        
        # 🟢 传递学生信息映射
        process_loop(driver, scores_data, student_info_map)
        
        print("\n🎉🎉🎉 所有回填操作已完成！")

    except Exception as e:
        print(f"❌ 任务异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("✅ 浏览器将在 10 秒后关闭...")
        time.sleep(10)
        try: driver.quit()
        except: pass

def ensure_list_frame_robust(driver):
    """列表页专用的 Frame 确保函数 (保持 test_relay_grading 的逻辑)"""
    time.sleep(0.5)
    driver.switch_to.default_content()
    try:
        # 尝试切入标准列表 Frame
        try:
            WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
            WebDriverWait(driver, 1).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
        except:
            driver.switch_to.default_content()
            WebDriverWait(driver, 1).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
        
        # 检查是否真的切进去了
        if len(driver.find_elements(By.CSS_SELECTOR, "ul.dataBody_td")) > 0:
            return True
    except: pass
    
    # 如果上面失败了，尝试旧的轮询方法作为兜底
    frame_combinations = [["frame_content"], ["frame_content-ks"]]
    for combo in frame_combinations:
        try:
            driver.switch_to.default_content()
            for f in combo: driver.switch_to.frame(f)
            if len(driver.find_elements(By.CSS_SELECTOR, "ul.dataBody_td")) > 0: return True
        except: pass
    return False

def fill_comment_ueditor(driver, feedback):
    """UEditor 专用填分逻辑"""
    try:
        # 1. 视觉触发
        trigger_input = None
        try:
            trigger_input = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input.kark_comment_text, .kark_comment_input input"))
            )
        except: pass
            
        if trigger_input:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger_input)
                try: trigger_input.click()
                except: driver.execute_script("arguments[0].click();", trigger_input)
                time.sleep(0.5)
                
                editor_frame = None
                frames = driver.find_elements(By.TAG_NAME, "iframe")
                for fr in frames:
                    if "ueditor" in (fr.get_attribute("id") or ""):
                        editor_frame = fr
                        break
                if not editor_frame:
                    try: editor_frame = driver.find_element(By.CSS_SELECTOR, ".edui-editor-iframeholder iframe")
                    except: pass

                if editor_frame:
                    driver.switch_to.frame(editor_frame)
                    try:
                        editor_body = driver.find_element(By.TAG_NAME, "body")
                        editor_body.clear()
                        editor_body.send_keys(feedback)
                    except: pass
                    driver.switch_to.default_content()
            except: 
                driver.switch_to.default_content()
        
        # 2. 绝杀：Shadow Write
        hidden_area = None
        try:
            hidden_area = driver.find_element(By.CSS_SELECTOR, "textarea[name^='teacherContent']")
        except:
            try: hidden_area = driver.find_element(By.CSS_SELECTOR, ".kark_comment_edit textarea")
            except: pass
        
        if hidden_area:
            print(f"      💉 执行数据强制同步 (Shadow Write)...")
            js_force_value = """
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input'));
                arguments[0].dispatchEvent(new Event('change'));
                arguments[0].dispatchEvent(new Event('blur'));
            """
            driver.execute_script(js_force_value, hidden_area, feedback)
            return True
        return False if not trigger_input else True
    except Exception as e:
        driver.switch_to.default_content()
        print(f"      ⚠️ 评语模块异常: {e}")
        return False

def fill_one_student(driver, score, feedback):
    try:
        # 1. 填分数
        inp = None
        try:
            inp = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.questionScore"))
            )
        except:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(iframes[0])
                try: inp = driver.find_element(By.CSS_SELECTOR, "input.questionScore")
                except: pass
        
        if not inp: 
            js_query = "return document.querySelector('input.questionScore') || document.querySelector('input[name*=\"score\"]')"
            inp = driver.execute_script(js_query)

        if not inp: raise Exception("未找到分数框")

        driver.execute_script("arguments[0].style.backgroundColor = '#ffff00';", inp)
        driver.execute_script("arguments[0].value = arguments[1]", inp, str(score))
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
        
        # 2. 填评语
        if feedback:
            fill_comment_ueditor(driver, feedback)

        # 3. 提交
        try:
            submit_btn = driver.find_element(By.XPATH, "//a[contains(text(), '提交') and not(contains(text(), '下一份'))]")
            driver.execute_script("arguments[0].click();", submit_btn)
            
            try:
                confirm_btn = WebDriverWait(driver, 1.5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.confirmHref, a.layui-layer-btn0"))
                )
                driver.execute_script("arguments[0].click();", confirm_btn)
            except: pass
            
            print("      ✅ 提交动作完成")
            # 🟢 提交完成时不在这里更新状态，由 process_loop 统一更新（因为这里没有学生信息）
            return True
        except:
            return False
    except Exception as e:
        print(f"      ⚠️ 填分出错: {e}")
        return False

def process_loop(driver, scores_data, student_info_map=None):
    """极简循环逻辑"""
    if student_info_map is None:
        student_info_map = {}
    
    remaining_ids = set(scores_data.keys())
    total = len(scores_data)
    completed_count = 0  # 🟢 修复：变量名与后续使用保持一致
    print(f"\n   🔄 开始名单匹配，待填 {total} 人...")
    
    # 🟢 初始化状态
    write_fill_state("fill_score_running", "开始回填分数", current_index=0, total=total)
    
    main_window_handle = driver.current_window_handle
    ensure_list_frame_robust(driver)
    
    while len(remaining_ids) > 0:
        print(f"      📄 扫描当前页...")
        
        if not ensure_list_frame_robust(driver):
            try:
                page_active = driver.find_element(By.CSS_SELECTOR, "li.active")
                driver.execute_script("arguments[0].click();", page_active)
                time.sleep(2)
            except: pass

        found_on_page = []
        for s_id in list(remaining_ids):
            xpath = f"//ul[contains(@class,'dataBody_td')]//li[contains(text(), '{s_id}')] | //ul[contains(@class,'dataBody_td')]//li[@title='{s_id}']"
            if len(driver.find_elements(By.XPATH, xpath)) > 0:
                found_on_page.append(s_id)
        
        if not found_on_page:
            print("         -> 本页无目标，尝试翻页")
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "li.xl-nextPage")
                if "disabled" in next_btn.get_attribute("class") or "xl-disabled" in next_btn.get_attribute("class"):
                    print("         🏁 已到最后一页，扫描结束。")
                    break
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(2)
                continue
            except: 
                print("         ❌ 翻页失败或已到头")
                break

        print(f"         ✅ 本页发现 {len(found_on_page)} 人: {found_on_page}")

        for s_id in found_on_page:
            try:
                btn_xpath = f"//ul[contains(@class,'dataBody_td')][.//li[contains(text(), '{s_id}')]]//a[contains(@class, 'cz_py')]"
                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, btn_xpath)))
                
                old_handles = driver.window_handles
                driver.execute_script("arguments[0].click();", btn)
                
                try:
                    WebDriverWait(driver, 10).until(EC.new_window_is_opened(old_handles))
                    new_handles = driver.window_handles
                    new_window = [h for h in new_handles if h not in old_handles][0]
                    driver.switch_to.window(new_window)
                except:
                    print(f"         ❌ 未检测到新窗口，跳过学生 {s_id}")
                    continue

                data = scores_data[s_id]
                # 🟢 更新状态：当前处理的学生（显示姓名+学号）
                student_name = student_info_map.get(s_id, '')
                student_display = f"{student_name} ({s_id})" if student_name else s_id
                
                write_fill_state(
                    "fill_score_running", 
                    f"正在回填学生 {student_display} 的成绩",
                    current_student=student_display,  # 🟢 显示姓名+学号（闪动效果）
                    current_index=completed_count,  # 🟢 已完成的数量（还未开始处理当前学生）
                    total=total
                )
                
                success = fill_one_student(driver, data['score'], data['feedback'])
                
                if success:
                    remaining_ids.remove(s_id)
                    completed_count += 1  # 🟢 修复：完成后数量+1
                    # 🟢 更新状态：提交完成（显示姓名+学号）
                    write_fill_state(
                        "fill_score_running",
                        f"✅ 学生 {student_display} 提交完成 ({completed_count}/{total})",
                        current_student=student_display,  # 🟢 仍然显示当前学生（用于进度显示）
                        current_index=completed_count,  # 🟢 已完成的数量（包含当前学生）
                        total=total
                    )
                    print(f"      ✅ 提交动作完成 [{completed_count}/{total}] - {student_display}")  # 🟢 添加进度显示和学生信息
                    time.sleep(0.5) 
                else:
                    print(f"         ❌ 学生 {s_id} 填分失败")

                try: driver.close()
                except: pass
                
                driver.switch_to.window(main_window_handle)
                ensure_list_frame_robust(driver)
                
            except Exception as e:
                print(f"         ⚠️ 处理异常: {e}")
                try:
                    if len(driver.window_handles) > 1 and driver.current_window_handle != main_window_handle:
                        driver.close()
                    driver.switch_to.window(main_window_handle)
                except: pass
                ensure_list_frame_robust(driver)

    if remaining_ids:
        print(f"⚠️ 警告: 有 {len(remaining_ids)} 名学生未找到: {remaining_ids}")
        success_count = total - len(remaining_ids)
        failed_count = len(remaining_ids)
        # 🟢 更新状态：部分完成，包含成功和失败数量
        write_fill_state(
            "fill_score_partial",
            f"回填完成，成功 {success_count} 个，失败 {failed_count} 个",
            current_index=success_count,
            total=total,
            success_count=success_count,  # 🟢 新增：成功数量
            failed_count=failed_count,  # 🟢 新增：失败数量
            missing_students=list(remaining_ids)
        )
    else:
        # 🟢 更新状态：全部完成，包含成功数量
        write_fill_state(
            "fill_score_completed",
            f"回填完成！成功 {total} 个",
            current_index=total,
            total=total,
            success_count=total,  # 🟢 新增：成功数量
            failed_count=0  # 🟢 新增：失败数量
        )
    return remaining_ids

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", required=True)
    parser.add_argument("--exam", required=True)
    parser.add_argument("--scores-file", required=True)
    parser.add_argument("--class-name", required=False, help="指定要回填的班级名称（可选）")  # 🟢 新增：班级名称参数
    parser.add_argument("--student-info-file", required=False, help="学生信息映射文件（可选）")  # 🟢 新增：学生信息文件
    args = parser.parse_args()
    
    run_grading_task(args.course, args.exam, args.scores_file, args.class_name, args.student_info_file)  # 🟢 传递班级名称和学生信息文件
