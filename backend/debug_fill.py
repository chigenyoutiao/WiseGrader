import os
import json
import sys
import subprocess
from pathlib import Path

# ================= 配置区域 =================
# 1. 课程和考试名称 (必须和学习通网页上的一字不差)
TARGET_COURSE = "智能合约设计与开发"
TARGET_EXAM = "期末考试"

# 2. 伪造的成绩单
# 格式: "学号": {"score": 分数, "feedback": "评语"}
# ⚠️ 请确保这些学号真实存在于你的班级里，否则脚本会找不到人
MOCK_DATA = {
    "2022105450015": {"score": 96, "feedback": "aaa"},
    "2022102160130": {"score": 85.5, "feedback": "bbb"},
    "2022105450022": {"score": 70, "feedback": "ccc"},
    # 你可以加更多...
}
# ===========================================

def run_debug():
    print("🔧 [Debug] 启动模拟回填测试...")
    
    # 1. 确定路径
    base_dir = Path(__file__).parent.resolve() # backend目录
    temp_dir = base_dir / "temp"
    script_path = base_dir / "xxt" / "grader.py"
    
    # 确保 temp 目录存在
    if not temp_dir.exists():
        temp_dir.mkdir()
        
    # 2. 生成伪造的成绩单文件
    json_path = temp_dir / "debug_scores.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(MOCK_DATA, f, ensure_ascii=False, indent=2)
        print(f"✅ 已生成伪造战绩: {json_path}")
        print(f"   包含学生: {list(MOCK_DATA.keys())}")
    except Exception as e:
        print(f"❌ 生成 JSON 失败: {e}")
        return

    # 3. 检查 grader.py 是否存在
    if not script_path.exists():
        print(f"❌ 找不到执行脚本: {script_path}")
        return

    # 4. 召唤 grader.py
    # 这完全模拟了 app.py 的调用方式
    cmd = [
        sys.executable, 
        str(script_path),
        "--course", TARGET_COURSE,
        "--exam", TARGET_EXAM,
        "--scores-file", str(json_path)
    ]
    
    print("-" * 50)
    print(f"🚀 开始执行命令: {' '.join(cmd)}")
    print("-" * 50)
    
    # 使用 subprocess.run 同步执行，这样我们可以看到实时输出
    try:
        subprocess.run(cmd, cwd=str(base_dir))
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断")
    except Exception as e:
        print(f"❌ 执行出错: {e}")

if __name__ == "__main__":
    run_debug()