"""Sky Companion - 游戏控制器
基于 SkyAutoMusic 验证的方案：psutil找窗口 + HWND_TOPMOST + keyboard库
"""

import time
import ctypes
import ctypes.wintypes
import psutil
import pygetwindow as gw
from config import KEYS, SKY_WINDOW_TITLES

user32 = ctypes.windll.user32

# ── 常量 ──
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001


def activate_sky_window():
    """找光遇窗口并强制置顶（SkyAutoMusic 方案）"""
    # 方法1: 通过进程名找（更准）
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name'].lower()
            if 'sky' in name or '光遇' in name:
                # 通过 PID 找窗口
                for win in gw.getAllWindows():
                    if win._hWnd and proc.info['pid'] == _get_pid_from_hwnd(win._hWnd):
                        _force_foreground(win._hWnd)
                        return win._hWnd
        except: pass
    
    # 方法2: 通过标题找
    for title_prefix in SKY_WINDOW_TITLES:
        windows = gw.getWindowsWithTitle(title_prefix)
        if windows:
            _force_foreground(windows[0]._hWnd)
            return windows[0]._hWnd
    return None


def _get_pid_from_hwnd(hwnd):
    """从窗口句柄获取 PID"""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _force_foreground(hwnd):
    """多管齐下，强制窗口到前台"""
    # 1. 还原窗口
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.05)
    
    # 2. 附加到目标窗口的输入线程
    current_tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    target_tid = user32.GetWindowThreadProcessId(hwnd, None)
    user32.AttachThreadInput(current_tid, target_tid, True)
    
    # 3. 置顶 + 前台
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    time.sleep(0.05)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.SetFocus(hwnd)
    
    # 4. 取消附加
    user32.AttachThreadInput(current_tid, target_tid, False)
    time.sleep(0.1)


class GameController:
    """游戏控制器"""

    @staticmethod
    def _key_name(key_name):
        return KEYS.get(key_name, key_name)

    @staticmethod
    def _focus():
        """每次操作前先激活窗口"""
        activate_sky_window()

    @staticmethod
    def press_key(key_name, duration=0.1):
        import keyboard
        GameController._focus()
        k = GameController._key_name(key_name)
        keyboard.press(k)
        time.sleep(duration)
        keyboard.release(k)

    @staticmethod
    def hold_key(key_name, duration=0.5):
        import keyboard
        GameController._focus()
        k = GameController._key_name(key_name)
        keyboard.press(k)
        time.sleep(duration)
        keyboard.release(k)

    @staticmethod
    def tap_key(key_name, times=1, interval=0.1):
        import keyboard
        GameController._focus()
        k = GameController._key_name(key_name)
        for _ in range(times):
            keyboard.press_and_release(k)
            time.sleep(interval)

    @staticmethod
    def move_forward(duration=1.0):
        GameController.hold_key("forward", duration)

    @staticmethod
    def move_backward(duration=1.0):
        GameController.hold_key("backward", duration)

    @staticmethod
    def move_left(duration=1.0):
        GameController.hold_key("left", duration)

    @staticmethod
    def move_right(duration=1.0):
        GameController.hold_key("right", duration)

    @staticmethod
    def fly(duration=1.0, boost=False):
        import keyboard
        GameController._focus()
        k = GameController._key_name("fly_up")
        keyboard.press(k)
        time.sleep(duration)
        keyboard.release(k)

    @staticmethod
    def jump(times=1):
        import keyboard
        GameController._focus()
        k = GameController._key_name("jump")
        for _ in range(times):
            keyboard.press_and_release(k)
            time.sleep(0.15)

    @staticmethod
    def interact():
        GameController._focus()
        GameController.tap_key("interact", 1, 0.1)

    @staticmethod
    def emote(number):
        import keyboard
        GameController._focus()
        key = f"emote_{number}"
        k = GameController._key_name(key)
        keyboard.press_and_release(k)

    @staticmethod
    def use_emote_by_name(name):
        from config import EMOTES
        if name in EMOTES:
            GameController.emote(EMOTES[name])

    @staticmethod
    def open_chat():
        import keyboard
        GameController._focus()
        keyboard.press_and_release("enter")
        time.sleep(0.3)

    @staticmethod
    def send_chat_message(text):
        import keyboard
        GameController._focus()
        keyboard.press_and_release("enter")
        time.sleep(0.3)
        keyboard.write(text, delay=0.02)
        time.sleep(0.2)
        keyboard.press_and_release("enter")

    @staticmethod
    


    @staticmethod
    def look_around(dx=300, dy=0):
        """视角转向（通过鼠标模拟）"""
        import ctypes
        ctypes.windll.user32.mouse_event(1, dx, dy, 0, 0)
def wait(seconds):
        time.sleep(seconds)
