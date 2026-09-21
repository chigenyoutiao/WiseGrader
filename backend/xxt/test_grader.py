import time
import json
import os
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= 基础配置 =================
TEST_COURSE = "测试班级"
TEST_EXAM = "期末考试"

# 待回填数据 (包含班级1和班级2的学生)
TEST_DATA = {
    # --- 班级 2 ---
    "20414": {"name": "张娜娜", "score": "88", "feedback": "测试评语：优秀 (By Script)"},
    "2023105450114": {"name": "李宜诺", "score": "90", "feedback": "测试评语：良好 (By Script)"},
    # --- 班级 1 ---
    "2022108600038": {"name": "鲁潇蔚", "score": "85", "feedback": "测试评语：继续努力 (By Script)"},
    "2023105450118": {"name": "贾雨杭", "score": "92", "feedback": "测试评语：非常棒 (By Script)"}
}

# ================= 环境引入 =================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # backend 根目录
for path in (current_dir, parent_dir):
    if path not in sys.path:
        sys.path.insert(0, path)

from xxt.browser import create_driver
from xxt.grader import InternalAuth, enter_course_robust, recursive_find_element, matches_target_value

# ================= 核心功能函数 =================

def go_to_exam_tab(driver):
    """进入课程左侧的【考试】栏目 (修复默认进不去的问题)"""
    print("   🧭 [导航] 正在点击侧边栏【考试】...")
    driver.switch_to.default_content()
    xpaths = [
        "//a[contains(@onclick,'toExamList')]",
        "//a[@title='考试']",
        "//li[.//span[contains(text(),'考试')]]//a",
        "//a[contains(text(),'考试') and not(contains(text(),'作业'))]"
    ]
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            # 验证
            driver.switch_to.default_content()
            try:
                WebDriverWait(driver, 3).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
                WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
                if driver.find_elements(By.CSS_SELECTOR, "h2.list_li_tit"):
                    print("   ✅ 已成功切换到考试列表")
                    return True
            except: pass
        except: continue
        finally: driver.switch_to.default_content()
    print("   ❌ 未能找到考试栏目")
    return False

def collect_class_titles(driver):
    """获取班级列表"""
    try:
        driver.switch_to.default_content()
        dropdown = recursive_find_element(driver, (By.CSS_SELECTOR, "a.banji_select_name"))
        if not dropdown:
            return ["当前班级"]
        driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(1)
        titles = [opt.get_attribute("title") or opt.text for opt in driver.find_elements(By.CSS_SELECTOR, "li.classli")]
        # 收起下拉
        try: driver.execute_script("arguments[0].click();", dropdown)
        except: pass
        # 去重并过滤空值
        return list(dict.fromkeys([t.strip() for t in titles if t]))
    except:
        return ["当前班级"]

def select_class(driver, title):
    """切换班级"""
    try:
        driver.switch_to.default_content()
        dropdown = recursive_find_element(driver, (By.CSS_SELECTOR, "a.banji_select_name"))
        if not dropdown: return False
        
        driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(0.5)
        
        xpath = f"//li[@title='{title}'] | //li[normalize-space(text())='{title}']"
        opt = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].click();", opt)
        print(f"      🔄 已切换到: {title}")
        time.sleep(2) # 等待刷新
        return True
    except:
        print(f"      ❌ 切换班级失败: {title}")
        return False

def enter_exam_in_current_view(driver, exam_name):
    """在当前列表找考试并点击批阅"""
    print(f"      🔎 扫描考试: {exam_name}")
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
        WebDriverWait(driver, 1).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
    except:
        driver.switch_to.default_content()
        try: WebDriverWait(driver, 1).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
        except: pass

    headers = driver.find_elements(By.CSS_SELECTOR, "h2.list_li_tit")
    for h in headers:
        if matches_target_value(exam_name, h.text, None):
            action_texts = ["批阅", "批改", "评阅"]
            for action in action_texts:
                try:
                    xpath = f"//li[.//h2[contains(text(), '{h.text.strip()}')]]//a[contains(text(), '{action}')]"
                    btn = driver.find_element(By.XPATH, xpath)
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"      ✅ 点击入口: [{action}]")
                    time.sleep(2)
                    return True
                except: continue
    print("      🔸 未找到该考试")
    return False

def real_fill_and_submit(driver, s_id, data):
    """真实填分并提交"""
    print(f"         ✍️ 正在填分: {data['name']} - {data['score']}分")
    try:
        # 1. 找输入框
        inp = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.questionScore"))
        )
        # 填分
        driver.execute_script("arguments[0].value = arguments[1]", inp, str(data['score']))
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", inp)
        
        # 2. 找提交按钮
        submit_btn = driver.find_element(By.XPATH, "//a[contains(text(), '提交') and not(contains(text(), '下一份'))]")
        driver.execute_script("arguments[0].click();", submit_btn)
        
        # 3. 处理确认弹窗
        try:
            confirm_btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.confirmHref, a.layui-layer-btn0"))
            )
            driver.execute_script("arguments[0].click();", confirm_btn)
        except: pass
        
        print("         ✅ 提交成功！")
        time.sleep(1) # 等待提交完成
        return True
    except Exception as e:
        print(f"         ❌ 填分/提交失败: {e}")
        return False

def process_class_students(driver, target_ids):
    """处理当前班级的学生"""
    processed = set()
    main_window = driver.current_window_handle
    
    # 确保在列表 Frame
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
        WebDriverWait(driver, 1).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
    except: pass

    # 扫描当前页
    for s_id in target_ids:
        xpath = f"//ul[contains(@class,'dataBody_td')][.//li[contains(text(), '{s_id}')]]//a[contains(@class, 'cz_py')]"
        try:
            # 找到批阅按钮
            btn = driver.find_element(By.XPATH, xpath)
            print(f"      👉 发现学生: {s_id}，打开批阅窗口...")
            driver.execute_script("arguments[0].click();", btn)
            
            # 切换到新窗口
            old_handles = driver.window_handles
            WebDriverWait(driver, 8).until(EC.new_window_is_opened(old_handles))
            new_window = [h for h in driver.window_handles if h not in old_handles][0]
            driver.switch_to.window(new_window)
            
            # === 执行真实填分 ===
            if real_fill_and_submit(driver, s_id, TEST_DATA[s_id]):
                processed.add(s_id)
            
            # 关闭窗口并切回
            driver.close()
            driver.switch_to.window(main_window)
            
            # 重新切 Frame
            driver.switch_to.default_content()
            try:
                WebDriverWait(driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
                WebDriverWait(driver, 1).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
            except: pass
            
        except:
            pass # 该学生不在当前页，继续找下一个

    return processed

# ================= 主流程 =================

def main():
    print("🚀 启动全流程测试脚本...")
    driver = create_driver(headless=False)
    auth = InternalAuth(driver, hide_window=False)
    
    if not auth.login(): return
    if not enter_course_robust(driver, TEST_COURSE): return
    
    # 1. 必须先去考试栏目，否则看不到下拉框
    if not go_to_exam_tab(driver): return

    # 2. 获取班级
    class_titles = collect_class_titles(driver)
    print(f"\n📋 扫描到班级: {class_titles}\n")

    all_targets = set(TEST_DATA.keys())
    processed_total = set()

    # 3. 开始遍历
    for cls in class_titles:
        print(f"🔹 [处理班级] {cls}")
        
        # 切换班级
        if cls != "当前班级":
            select_class(driver, cls)
            
        # 找考试
        if enter_exam_in_current_view(driver, TEST_EXAM):
            # 找本班学生
            current_pending = all_targets - processed_total
            done_in_class = process_class_students(driver, current_pending)
            
            if done_in_class:
                processed_total.update(done_in_class)
                print(f"      🎉 本班已完成: {done_in_class}")
            else:
                print("      🔸 本班未发现目标学生")
            
            # 重要：处理完一个班，退回到列表页，为下一次切换做准备
            driver.back()
            time.sleep(2)
        else:
            print("      🔸 未找到考试入口")

    print("\n" + "="*40)
    print(f"📊 测试报告")
    print(f"   目标总数: {len(all_targets)}")
    print(f"   成功回填: {len(processed_total)}")
    print(f"   未找到: {all_targets - processed_total}")
    print("="*40)
    
    time.sleep(5)
    driver.quit()

if __name__ == "__main__":
    main()
