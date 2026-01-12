"""
独立的提示框窗口脚本
通过 subprocess 启动，避免线程问题
"""
import sys
import tkinter as tk

def main():
    if len(sys.argv) < 2:
        print("Usage: python overlay_window.py <mode>")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    root = tk.Tk()
    root.overrideredirect(True)  # 无边框
    root.attributes('-topmost', True)  # 置顶
    root.attributes('-alpha', 0.9)  # 透明度
    
    # 获取屏幕尺寸
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # 窗口大小和位置（右下角）
    if mode == "recording":
        width, height = 180, 45
        bg_color = "#d32f2f"  # 红色
        text = "● 录制中 (ESC停止)"
    else:
        width, height = 120, 45
        bg_color = "#4CAF50"  # 绿色
        text = "▶ 执行中..."
    
    x = screen_width - width - 20
    y = screen_height - height - 80
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    root.configure(bg=bg_color)
    
    label = tk.Label(
        root, 
        text=text, 
        fg="white", 
        bg=bg_color,
        font=("Microsoft YaHei", 11, "bold")
    )
    label.pack(expand=True, fill='both')
    
    root.mainloop()

if __name__ == "__main__":
    main()
