import os
import json
import time
from selenium.webdriver.common.by import By

# 动态计算路径，确保能找到 backend 根目录下的 xxt_cookies.json
current_dir = os.path.dirname(os.path.abspath(__file__))
# core -> xxt -> backend
BASE_DIR = os.path.dirname(os.path.dirname(current_dir)) 
COOKIE_FILE = os.path.join(BASE_DIR, "xxt_cookies.json")

LOGIN_URL = 'https://passport2.chaoxing.com/login?fid=&newversion=true&refer=https%3A%2F%2Fi.chaoxing.com'
COURSE_URL = 'https://i.chaoxing.com/base'

class XXTAuth:
    def __init__(self, driver):
        self.driver = driver

    def load_cookies(self):
        """核心功能：从文件读取 Cookie 并注入浏览器"""
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, 'r') as f: 
                    cookies = json.load(f)
                
                # 1. 必须先访问一次 chaoxing.com 域名下的任意页面
                # 否则浏览器会拒绝接收 Cookie
                self.driver.get(LOGIN_URL)
                
                success_count = 0
                for c in cookies:
                    # 🔥 核心修复：删除 'domain' 和 'expiry' 字段
                    # 防止因为域名匹配过严或时间格式问题导致报错
                    if 'domain' in c: del c['domain']
                    if 'expiry' in c: del c['expiry']
                    if 'sameSite' in c: del c['sameSite'] # 有时候这个也会导致问题
                    
                    try:
                        self.driver.add_cookie(c)
                        success_count += 1
                    except Exception as e:
                        # 忽略个别坏掉的 Cookie，不要因为一个坏的就全部崩溃
                        # print(f"   ⚠️ 跳过无效 Cookie: {e}")
                        pass
                        
                print(f"   🍪 成功注入 {success_count}/{len(cookies)} 个 Cookie")
                return True
            except Exception as e:
                print(f"   ⚠️ Cookie 文件读取/注入异常: {e}")
        else:
            print(f"   ⚠️ 未找到 Cookie 文件: {COOKIE_FILE}")
        return False

    def save_cookies(self):
        """保存当前登录成功的 Cookie"""
        try:
            with open(COOKIE_FILE, 'w') as f:
                json.dump(self.driver.get_cookies(), f)
            print("   💾 Cookie 已更新并保存")
        except Exception as e:
            print(f"   ⚠️ Cookie 保存失败: {e}")

    def login(self):
        """智能登录逻辑"""
        print("   🔑 启动登录流程...")
        
        # 1. 尝试 Cookie 免登
        if self.load_cookies():
            # 注入完 Cookie 后，刷新或跳转到目标页
            self.driver.get(COURSE_URL)
            time.sleep(2)
            
            # 检查是否还在登录页 (如果 URL 包含 passport2 说明被踢回来了)
            if "passport2.chaoxing.com" not in self.driver.current_url:
                print("   ✅ Cookie 有效，免密登录成功！")
                return True
            else:
                print("   ⚠️ Cookie 已失效或被服务端拒绝，切换到扫码模式")
        
        # 2. 扫码登录 (作为兜底)
        if "passport2.chaoxing.com" not in self.driver.current_url:
             self.driver.get(LOGIN_URL)
             
        print("   📸 [交互] 请在浏览器中扫描二维码...")
        
        # 循环检测登录状态 (最多等 5 分钟)
        end_time = time.time() + 300 
        while time.time() < end_time:
            # 如果跳转到了 i.chaoxing.com 或者其他非登录页，说明成功
            if "passport2.chaoxing.com" not in self.driver.current_url:
                print("   ✅ 扫码成功！")
                self.save_cookies() # 马上保存新的，下次就能用了
                return True
            time.sleep(1)
            
        print("   ❌ 登录超时")
        return False