"""
简化的自动化播放器
使用 pyautogui 进行鼠标和键盘操作
"""
import time
import threading
import ctypes
import pyautogui
import atexit
from pynput import keyboard
from pynput.keyboard import Key

# 设置 DPI 感知（修复高分辨率屏幕坐标偏移）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

# 配置 pyautogui
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.005

# 按键名称映射（录制时的名称 -> pyautogui 的名称）
KEY_MAP = {
    'space': 'space', 'enter': 'enter', 'tab': 'tab',
    'backspace': 'backspace', 'delete': 'delete',
    'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
    'home': 'home', 'end': 'end', 'page_up': 'pageup', 'page_down': 'pagedown',
    'shift': 'shift', 'shift_l': 'shiftleft', 'shift_r': 'shiftright',
    'ctrl': 'ctrl', 'ctrl_l': 'ctrlleft', 'ctrl_r': 'ctrlright',
    'alt': 'alt', 'alt_l': 'altleft', 'alt_r': 'altright', 'alt_gr': 'altright',
    'win': 'win', 'win_l': 'winleft', 'win_r': 'winright',
    'cmd': 'win', 'cmd_l': 'winleft', 'cmd_r': 'winright',
    'caps_lock': 'capslock', 'num_lock': 'numlock',
    'esc': 'escape', 'escape': 'escape',
    'insert': 'insert',
    'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
    'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
    'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
}

# 所有修饰键列表（用于强制释放）
ALL_MODIFIER_KEYS = [
    'shift', 'shiftleft', 'shiftright',
    'ctrl', 'ctrlleft', 'ctrlright',
    'alt', 'altleft', 'altright',
    'win', 'winleft', 'winright',
]

def map_key(key_name):
    """将录制的按键名称映射为 pyautogui 可识别的名称"""
    if not key_name:
        return None
    if len(key_name) == 1 and key_name.isprintable():
        return key_name
    return KEY_MAP.get(key_name.lower(), key_name.lower())

def force_release_all_keys():
    """强制释放所有修饰键"""
    for key in ALL_MODIFIER_KEYS:
        try:
            pyautogui.keyUp(key)
        except:
            pass

atexit.register(force_release_all_keys)


class SimplePlayer:
    """简化的播放器类"""
    
    def __init__(self):
        self.is_playing = False
        self.thread = None
        self.pressed_keys = set()
        self._lock = threading.Lock()
        self.overlay_process = None
        self.stop_requested = False
        self.keyboard_listener = None
        self.current_loop = 0
        self.total_loops = 1
    
    def play(self, events, speed=1.0, loop_count=1):
        """播放事件"""
        if not events:
            print("无事件可播放")
            return False
        
        if self.is_playing:
            print("已有任务在播放中")
            return False
        
        self.is_playing = True
        self.stop_requested = False
        self.pressed_keys.clear()
        self.current_loop = 0
        self.total_loops = loop_count
        
        print(f"开始播放 {len(events)} 个事件，速度 {speed}x，循环 {loop_count} 次...")
        
        # 显示提示框
        self._show_overlay()
        
        # 启动 ESC 监听
        self._start_esc_listener()
        
        # 回到桌面
        self._go_to_desktop()
        
        # 启动播放线程
        self.thread = threading.Thread(target=self._play_events_safe, args=(events, speed, loop_count))
        self.thread.start()
        
        return True
    
    def stop(self):
        """停止播放"""
        self.stop_requested = True
        self.is_playing = False
        self._stop_esc_listener()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        
        self._hide_overlay()
        self._release_all_keys()
        print("播放已停止")
    
    def _start_esc_listener(self):
        """启动 ESC 键监听"""
        def on_press(key):
            if key == Key.esc and self.is_playing:
                print("\n>>> ESC 中断播放")
                self.stop_requested = True
                return False
        
        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()
    
    def _stop_esc_listener(self):
        """停止 ESC 键监听"""
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass
            self.keyboard_listener = None
    
    def _show_overlay(self):
        """显示提示框"""
        try:
            import subprocess
            import os
            script_path = os.path.join(os.path.dirname(__file__), "overlay_window.py")
            self.overlay_process = subprocess.Popen(
                ["python", script_path, "playing"],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception as e:
            print(f"显示提示框失败: {e}")
    
    def _hide_overlay(self):
        """隐藏提示框"""
        if self.overlay_process:
            try:
                self.overlay_process.terminate()
                self.overlay_process = None
            except:
                pass
    
    def _go_to_desktop(self):
        """回到桌面"""
        try:
            time.sleep(0.3)
            pyautogui.hotkey('win', 'd')
            time.sleep(0.5)
        except Exception as e:
            print(f"回到桌面失败: {e}")
    
    def _back_to_browser(self):
        """回到浏览器"""
        try:
            time.sleep(0.3)
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.3)
        except Exception as e:
            print(f"回到浏览器失败: {e}")
    
    def _play_events_safe(self, events, speed, loop_count):
        """安全的播放线程"""
        try:
            for loop in range(loop_count):
                if self.stop_requested:
                    print(f"循环被中断，已完成 {loop}/{loop_count} 次")
                    break
                
                self.current_loop = loop + 1
                print(f"\n=== 第 {self.current_loop}/{loop_count} 次循环 ===")
                
                self._play_events(events, speed)
                
                # 循环间隔
                if loop < loop_count - 1 and not self.stop_requested:
                    time.sleep(0.5)
            
            if not self.stop_requested:
                print(f"\n播放完成！共执行 {loop_count} 次")
        except Exception as e:
            print(f"播放错误: {e}")
        finally:
            self._stop_esc_listener()
            self._release_all_keys()
            self._hide_overlay()
            self._back_to_browser()
            self.is_playing = False
    
    def _play_events(self, events, speed):
        """播放单次事件"""
        last_time = 0
        
        for i, event in enumerate(events):
            if self.stop_requested:
                break
            
            try:
                event_time = event.get("time", 0)
                delay = (event_time - last_time) / speed
                
                if 0 < delay < 5:
                    # 分段等待，便于响应中断
                    wait_end = time.time() + delay
                    while time.time() < wait_end and not self.stop_requested:
                        time.sleep(0.05)
                
                if self.stop_requested:
                    break
                
                last_time = event_time
                event_type = event.get("type")
                
                if event_type == "mouse_click":
                    self._play_mouse_click(event)
                elif event_type == "mouse_move":
                    self._play_mouse_move(event)
                elif event_type == "mouse_scroll":
                    self._play_mouse_scroll(event)
                elif event_type == "key_press":
                    self._play_key_press(event)
                elif event_type == "key_release":
                    self._play_key_release(event)
                elif event_type == "wait":
                    self._play_wait(event, speed)
                elif event_type == "input_text":
                    self._play_input_text(event)
                
            except Exception as e:
                print(f"事件{i+1}出错: {e}")
    
    def _play_mouse_click(self, event):
        x, y = int(event.get("x", 0)), int(event.get("y", 0))
        button = event.get("button", "left")
        pressed = event.get("pressed", False)
        pyautogui.moveTo(x, y, duration=0.01)
        if pressed:
            pyautogui.mouseDown(button=button)
        else:
            pyautogui.mouseUp(button=button)
    
    def _play_mouse_move(self, event):
        x, y = int(event.get("x", 0)), int(event.get("y", 0))
        pyautogui.moveTo(x, y, duration=0.01)
    
    def _play_mouse_scroll(self, event):
        x, y = int(event.get("x", 0)), int(event.get("y", 0))
        dy = event.get("dy", 0)
        pyautogui.moveTo(x, y, duration=0.01)
        if dy:
            pyautogui.scroll(int(dy))
    
    def _play_key_press(self, event):
        key = map_key(event.get("key"))
        if key:
            try:
                pyautogui.keyDown(key)
                with self._lock:
                    self.pressed_keys.add(key)
            except:
                pass
    
    def _play_key_release(self, event):
        key = map_key(event.get("key"))
        if key:
            try:
                pyautogui.keyUp(key)
                with self._lock:
                    self.pressed_keys.discard(key)
            except:
                pass
    
    def _play_wait(self, event, speed):
        """播放等待事件"""
        duration = event.get("duration", 1) / speed
        wait_end = time.time() + duration
        while time.time() < wait_end and not self.stop_requested:
            time.sleep(0.05)
    
    def _play_input_text(self, event):
        """播放输入文本事件"""
        text = event.get("text", "")
        if text:
            pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
    
    def _release_all_keys(self):
        """释放所有按键"""
        time.sleep(0.1)
        with self._lock:
            for key in list(self.pressed_keys):
                try:
                    pyautogui.keyUp(key)
                except:
                    pass
            self.pressed_keys.clear()
        
        for key in ALL_MODIFIER_KEYS:
            try:
                pyautogui.keyUp(key)
            except:
                pass


_global_player = None

def get_player():
    global _global_player
    if _global_player is None:
        _global_player = SimplePlayer()
    return _global_player
