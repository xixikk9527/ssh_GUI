"""
简化的自动化录制器
使用 pynput 库进行鼠标和键盘监听
"""
import time
import threading
import ctypes
from pynput import mouse, keyboard
from pynput.mouse import Button
from pynput.keyboard import Key, Listener

# 设置 DPI 感知（修复高分辨率屏幕坐标偏移）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

class SimpleRecorder:
    """简化的录制器类"""
    
    def __init__(self):
        self.is_recording = False
        self.events = []
        self.start_time = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.stop_event = threading.Event()
        self.mouse_pressed = False  # 跟踪鼠标按下状态（用于拖拽）
        self.last_move_time = 0
        self.MOVE_INTERVAL = 0.05  # 鼠标移动记录间隔
        self.record_mouse_move = False  # 是否记录鼠标移动轨迹
        self.overlay = None  # 提示框窗口
    
    def start(self, record_mouse_move=False):
        """开始录制（同步启动监听器）
        
        Args:
            record_mouse_move: 是否记录鼠标移动轨迹
        """
        if self.is_recording:
            return False
        
        self.is_recording = True
        self.events = []
        self.start_time = time.time()
        self.stop_event.clear()
        self.mouse_pressed = False
        self.last_move_time = 0
        self.record_mouse_move = record_mouse_move
        
        print(f"录制开始... (按ESC停止) [记录鼠标轨迹: {record_mouse_move}]")
        
        # 显示录制提示框
        self._show_overlay("recording")
        
        # 回到桌面
        self._go_to_desktop()
        
        # 直接启动监听器（不在子线程中）
        self._start_listeners()
        
        return True
    
    def stop(self):
        """停止录制"""
        if not self.is_recording:
            return False
        
        self.is_recording = False
        self.stop_event.set()
        
        # 隐藏提示框
        self._hide_overlay()
        
        # 停止监听器
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except:
                pass
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass
        
        duration = time.time() - self.start_time if self.start_time else 0
        print(f"录制完成！{len(self.events)}个事件，时长{duration:.2f}秒")
        
        return {
            "events": self.events,
            "duration": round(duration, 2)
        }
    
    def _show_overlay(self, mode="recording"):
        """显示提示框（独立进程）"""
        try:
            import subprocess
            import os
            script_path = os.path.join(os.path.dirname(__file__), "overlay_window.py")
            self.overlay_process = subprocess.Popen(
                ["python", script_path, mode],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception as e:
            print(f"显示提示框失败: {e}")
            self.overlay_process = None
    
    def _hide_overlay(self):
        """隐藏提示框"""
        if hasattr(self, 'overlay_process') and self.overlay_process:
            try:
                self.overlay_process.terminate()
                self.overlay_process = None
            except:
                pass
    
    def _go_to_desktop(self):
        """回到桌面（Win+D）"""
        try:
            import pyautogui
            time.sleep(0.3)  # 等待一下
            pyautogui.hotkey('win', 'd')
            time.sleep(0.5)  # 等待桌面显示
        except Exception as e:
            print(f"回到桌面失败: {e}")
    
    def _back_to_browser(self):
        """回到浏览器（Alt+Tab）"""
        try:
            import pyautogui
            time.sleep(0.3)
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.3)
        except Exception as e:
            print(f"回到浏览器失败: {e}")
    
    def _start_listeners(self):
        """启动监听器"""
        # 鼠标事件处理
        def on_click(x, y, button, pressed):
            if not self.is_recording:
                return False
            
            self.mouse_pressed = pressed
            btn_name = "left" if button == Button.left else "right" if button == Button.right else "middle"
            self.events.append({
                "type": "mouse_click",
                "time": time.time() - self.start_time,
                "x": x,
                "y": y,
                "button": btn_name,
                "pressed": pressed
            })
            print(f"  鼠标{btn_name} {'↓' if pressed else '↑'} ({x},{y})")
        
        def on_move(x, y):
            """记录鼠标移动"""
            if not self.is_recording:
                return
            
            # 只在拖拽时或开启了鼠标轨迹记录时才记录
            if not self.mouse_pressed and not self.record_mouse_move:
                return
            
            now = time.time()
            if now - self.last_move_time >= self.MOVE_INTERVAL:
                self.last_move_time = now
                self.events.append({
                    "type": "mouse_move",
                    "time": now - self.start_time,
                    "x": x,
                    "y": y
                })
                # 只在拖拽时打印，避免日志过多
                if self.mouse_pressed:
                    print(f"  拖拽 ({x},{y})")
        
        def on_scroll(x, y, dx, dy):
            if not self.is_recording:
                return False
            
            self.events.append({
                "type": "mouse_scroll",
                "time": time.time() - self.start_time,
                "x": x,
                "y": y,
                "dx": dx,
                "dy": dy
            })
            print(f"  滚轮 {dy}")
        
        # 键盘事件处理
        def on_press(key):
            if not self.is_recording:
                return False
            
            # ESC键停止录制
            if key == Key.esc:
                print("\n>>> ESC 停止录制")
                self.is_recording = False
                self.stop_event.set()
                # 隐藏提示框
                self._hide_overlay()
                # 回到浏览器
                self._back_to_browser()
                return False  # 停止键盘监听器
            
            key_name = self._key_to_name(key)
            if key_name:
                self.events.append({
                    "type": "key_press",
                    "time": time.time() - self.start_time,
                    "key": key_name
                })
                print(f"  按键↓ '{key_name}'")
        
        def on_release(key):
            if not self.is_recording:
                return False
            
            if key == Key.esc:
                return False
            
            key_name = self._key_to_name(key)
            if key_name:
                self.events.append({
                    "type": "key_release",
                    "time": time.time() - self.start_time,
                    "key": key_name
                })
        
        # 启动监听器
        self.mouse_listener = mouse.Listener(
            on_click=on_click,
            on_scroll=on_scroll,
            on_move=on_move
        )
        self.mouse_listener.start()
        
        self.keyboard_listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self.keyboard_listener.start()
    
    def _key_to_name(self, key):
        """转换按键为名称"""
        # 特殊键映射
        special_keys = {
            Key.space: 'space',
            Key.enter: 'enter',
            Key.tab: 'tab',
            Key.backspace: 'backspace',
            Key.delete: 'delete',
            Key.up: 'up',
            Key.down: 'down',
            Key.left: 'left',
            Key.right: 'right',
            Key.shift: 'shift',
            Key.ctrl: 'ctrl',
            Key.alt: 'alt',
            Key.cmd: 'win',
            Key.esc: 'esc',
            Key.f1: 'f1',
            Key.f2: 'f2',
            Key.f3: 'f3',
            Key.f4: 'f4',
            Key.f5: 'f5',
            Key.f6: 'f6',
            Key.f7: 'f7',
            Key.f8: 'f8',
            Key.f9: 'f9',
            Key.f10: 'f10',
            Key.f11: 'f11',
            Key.f12: 'f12',
        }
        
        if key in special_keys:
            return special_keys[key]
        
        # 字符键
        try:
            if hasattr(key, 'char') and key.char:
                return key.char
        except:
            pass
        
        return str(key).replace('Key.', '').lower()

# 全局录制器实例
_global_recorder = None

def get_recorder():
    """获取全局录制器实例"""
    global _global_recorder
    if _global_recorder is None:
        _global_recorder = SimpleRecorder()
    return _global_recorder