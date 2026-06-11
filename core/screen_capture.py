# -*- coding: utf-8 -*-
"""
Sky Companion - 屏幕捕获模块
"""

import os
import time
import pygetwindow as gw
import pyautogui
from PIL import Image
from config import SKY_WINDOW_TITLES, SCREENSHOT_DIR

def find_sky_window():
    """查找光遇游戏窗口"""
    all_windows = gw.getAllTitles()
    for title in all_windows:
        for sky_title in SKY_WINDOW_TITLES:
            if sky_title in title:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    return windows[0]
    return None

def get_window_rect(window):
    """获取窗口矩形区域"""
    try:
        if window.isMinimized:
            window.restore()
        return {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }
    except Exception:
        return None

def capture_window(window=None):
    """捕获光遇窗口截图"""
    if window is None:
        window = find_sky_window()

    if window is None:
        return None

    rect = get_window_rect(window)
    if rect is None:
        return None

    screenshot = pyautogui.screenshot(
        region=(rect["left"], rect["top"], rect["width"], rect["height"])
    )
    return screenshot

def capture_fullscreen():
    """捕获全屏截图"""
    return pyautogui.screenshot()

def save_screenshot(screenshot, prefix="sky"):
    """保存截图到文件"""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    screenshot.save(filepath)
    return filepath

def window_exists():
    """检查光遇窗口是否存在"""
    return find_sky_window() is not None
