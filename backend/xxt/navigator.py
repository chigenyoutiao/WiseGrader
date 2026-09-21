# 文件路径: backend/xxt/navigator.py
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class XXTNavigator:
    def __init__(self, driver):
        self.driver = driver

    def recursive_find_element(self, locator, depth=0):
        """全维度递归查找元素（用于找下拉框）"""
        try:
            if len(self.driver.find_elements(*locator)) > 0:
                return self.driver.find_element(*locator)
        except: pass

        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            try:
                self.driver.switch_to.frame(frame)
                found = self.recursive_find_element(locator, depth + 1)
                if found: return found
                self.driver.switch_to.parent_frame()
            except:
                self.driver.switch_to.parent_frame()
        return None

    def enter_course(self, course_name):
        """进入指定课程"""
        print(f"   🔍 正在进入课程: {course_name}")
        self.driver.get("https://i.chaoxing.com/base")
        # 简单等待登录检查...
        time.sleep(2)
        
        # 这里的逻辑可以复用你 main.py 里的找课逻辑，简化版如下：
        try:
            self.driver.switch_to.default_content()
            btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//div[@name='新版课程'] | //span[contains(text(),'新版课程')]")))
            self.driver.execute_script("arguments[0].click();", btn)
            WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
            
            course_link = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, course_name)))
            course_link.click()
            
            # 切换窗口
            self.switch_to_newest_window()
            return True
        except Exception as e:
            print(f"   ❌ 进入课程失败: {e}")
            return False

    def enter_exam_smart(self, exam_name):
        """傻瓜式轮询切班级找考试"""
        print(f"   🔍 开始在所有班级中查找考试: {exam_name}")
        
        # 1. 进考试栏目
        try:
            exam_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '考试') and not(contains(text(), '作业'))] | //a[@title='考试']"))
            )
            self.driver.execute_script("arguments[0].click();", exam_btn)
            time.sleep(2)
        except:
            print("   ⚠️ 点击'考试'栏目失败")
            return False

        # 2. 获取班级列表
        self.driver.switch_to.default_content()
        target_locator = (By.CSS_SELECTOR, "a.banji_select_name")
        dropdown_trigger = self.recursive_find_element(target_locator)
        
        if not dropdown_trigger:
            print("   ⚠️ 未找到班级下拉框，尝试直接在当前页找考试...")
            class_names = ["默认视图"]
        else:
            try:
                self.driver.execute_script("arguments[0].click();", dropdown_trigger)
                time.sleep(1)
                opts = self.driver.find_elements(By.CSS_SELECTOR, "li.classli")
                class_names = [o.get_attribute("title") for o in opts if o.get_attribute("title") and "全部" not in o.get_attribute("title")]
                # 收起
                self.driver.execute_script("arguments[0].click();", dropdown_trigger)
            except:
                class_names = ["默认视图"]

        print(f"   📦 待检查班级: {class_names}")

        # 3. 轮询
        for cls_name in class_names:
            print(f"   🔄 检查: {cls_name}")
            if cls_name != "默认视图":
                # 重新找下拉框切换
                self.driver.switch_to.default_content()
                dropdown = self.recursive_find_element(target_locator)
                if dropdown:
                    self.driver.execute_script("arguments[0].click();", dropdown)
                    time.sleep(0.5)
                    try:
                        target = self.driver.find_element(By.XPATH, f"//li[@title='{cls_name}']")
                        self.driver.execute_script("arguments[0].click();", target)
                        time.sleep(2)
                    except: pass

            # 找考试
            try:
                self.driver.switch_to.default_content()
                # 尝试切入不同层级
                try: WebDriverWait(self.driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content"))
                except: pass
                try: WebDriverWait(self.driver, 2).until(EC.frame_to_be_available_and_switch_to_it("frame_content-ks"))
                except: pass
                
                # 核心：找文字而非链接
                xpath = f"//*[contains(text(), '{exam_name}')]"
                if len(self.driver.find_elements(By.XPATH, xpath)) > 0:
                    print(f"   🎉 找到了！")
                    # 点击批阅
                    btn_xpath = f"//li[contains(., '{exam_name}')]//a[contains(text(), '批阅')]"
                    self.driver.find_element(By.XPATH, btn_xpath).click()
                    return True
            except: pass
            
        return False

    def switch_to_newest_window(self):
        handles = self.driver.window_handles
        self.driver.switch_to.window(handles[-1])

    def ensure_in_list_frame(self):
        """确保在列表页 Frame"""
        self.driver.switch_to.default_content()
        for f in ["frame_content-ks", "frame_content"]:
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(f)
                if len(self.driver.find_elements(By.CSS_SELECTOR, "ul.dataBody_td")) > 0:
                    return True
            except: pass
        return False