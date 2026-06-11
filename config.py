# -*- coding: utf-8 -*-
"""
Sky Companion - 光遇桌面伴侣代理
配置文件
"""

import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ========== 默认模型配置（不包含 API Key） ==========
DEFAULT_VISION_BASE_URL = "https://www.hohoapi.com/v1"
DEFAULT_VISION_MODEL = "gemini-2.5-flash"
DEFAULT_CHAT_BASE_URL = "https://api.deepseek.com"
DEFAULT_CHAT_MODEL = "deepseek-chat"

# ========== 光遇游戏窗口标题 ==========
SKY_WINDOW_TITLES = [
    "光·遇",
    "Sky: Children of the Light",
    "Sky",
    "光遇",
]

# ========== 截图配置 ==========
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "outputs", "screenshots")
SCREENSHOT_INTERVAL = 0.5
TEMPLATE_MATCH_THRESHOLD = 0.8

# ========== 键位配置（光遇默认键位） ==========
KEYS = {
    "forward": "w",
    "backward": "s",
    "left": "a",
    "right": "d",
    "fly_up": "space",
    "fly_boost": "shift",
    "jump": "space",
    "interact": "f",
    "menu": "esc",
    "camera_zoom_in": "pageup",
    "camera_zoom_out": "pagedown",
    "camera_reset": "home",
    "chat": "enter",
    "emote_menu": "1",
    "emote_1": "1",
    "emote_2": "2",
    "emote_3": "3",
    "emote_4": "4",
    "emote_5": "5",
    "emote_6": "6",
    "emote_7": "7",
}

# ========== 动作/表情对应 ==========
EMOTES = {
    "点头": 1,
    "挥手": 2,
    "鞠躬": 3,
    "坐下": 4,
    "大叫": 5,
    "牵手": 6,
    "拥抱": 7,
}

# ========== 三恋角色扮演模式 ==========
COMPANION_MODES = {
    "正常": {
        "style": "普通朋友，自然聊天，像游戏里的日常好友一样相处",
        "greeting": "嗨！今天跑图了吗？",
    },
    "虚恋": {
        "style": "虚拟恋爱，温柔体贴，像真正的恋人一样关心你、宠你",
        "greeting": "今天想我了吗？……我想你了。",
    },
    "病恋": {
        "style": "病娇，偏执深情，极强的占有欲和控制欲，你只能是我的",
        "greeting": "你去哪里了？我找了你好久……（笑）下次别这样了。",
    },
    "虐恋": {
        "style": "虐心，情感拉扯，爱而不得的痛感，若即若离的纠结",
        "greeting": "我们这样到底算什么……（苦笑）算了，能陪你就好。",
    },
}

DEFAULT_MODE = "正常"
