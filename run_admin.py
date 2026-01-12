"""
以管理员权限启动 Web 服务器
自动化录制功能需要管理员权限才能全局捕获键盘
"""
import sys
import os
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if sys.platform == 'win32':
        # 请求管理员权限重新运行
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, 
            f'"{os.path.abspath("main.py")}"', 
            os.getcwd(), 1
        )
        sys.exit(0)

if __name__ == "__main__":
    if not is_admin():
        print("需要管理员权限，正在请求...")
        run_as_admin()
    else:
        # 已经是管理员，直接运行
        print("以管理员权限运行服务器...")
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=False)
