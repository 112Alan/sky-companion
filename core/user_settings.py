# -*- coding: utf-8 -*-
"""Local-only first-run settings and memory helpers."""
import copy
import getpass
import json
import os
from datetime import datetime

from config import PROJECT_ROOT

USER_DATA_DIR = os.path.join(PROJECT_ROOT, "user_data")
SETTINGS_FILE = os.path.join(USER_DATA_DIR, "settings.json")
MEMORY_FILE = os.path.join(USER_DATA_DIR, "memory.json")

DEFAULT_SETTINGS = {
    "companion_name": "",
    "user_call_name": "",
    "personality_prompt": "",
    "vision": {
        "provider": "gemini",
        "base_url": "https://www.hohoapi.com/v1",
        "model": "gemini-2.5-flash",
        "api_key": "",
    },
    "chat": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "api_key": "",
    },
}


def _deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        return copy.deepcopy(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
            return _deep_merge(DEFAULT_SETTINGS, json.load(f))
    except Exception:
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    value = input(prompt + suffix + ": ").strip()
    return value or default


def _ask_secret(prompt):
    try:
        return getpass.getpass(prompt + ": ").strip()
    except Exception:
        return input(prompt + ": ").strip()


def _configure_model(settings, kind):
    is_vision = kind == "vision"
    label = "视觉识别模型"
    default_name = "Gemini"
    if not is_vision:
        label = "聊天回复模型"
        default_name = "DeepSeek"

    current = settings[kind]
    has_default = _ask(f"你有 {default_name} 的 API Key 吗？有就回车，没有输入 n", "y").lower()
    if has_default in ("n", "no", "没有", "mei", "0"):
        print(f"请填写自定义{label}，要求兼容 OpenAI Chat Completions 接口。")
        current["provider"] = "custom"
        current["base_url"] = ""
        current["model"] = ""
        while not current.get("base_url"):
            current["base_url"] = _ask("接口网址 base_url，例如 https://api.example.com/v1")
        while not current.get("model"):
            current["model"] = _ask("模型名")
    else:
        current["provider"] = "gemini" if is_vision else "deepseek"
        current["base_url"] = _ask("接口网址 base_url", current["base_url"])
        current["model"] = _ask("模型名", current["model"])

    while not current.get("api_key"):
        current["api_key"] = _ask_secret(f"{label} API Key")
        if not current["api_key"]:
            print("API Key 不能为空。")
    settings[kind] = current


def ensure_settings():
    settings = load_settings()

    if not settings["vision"].get("api_key"):
        _configure_model(settings, "vision")
        save_settings(settings)

    if not settings["chat"].get("api_key"):
        _configure_model(settings, "chat")
        save_settings(settings)

    if not settings.get("companion_name"):
        print("请给你的光遇伴侣命名！")
        settings["companion_name"] = input("伴侣名字: ").strip()
        if not settings["companion_name"]:
            save_settings(settings)
            print("请给你的光遇伴侣命名！")
            return None
        save_settings(settings)

    if not settings.get("user_call_name"):
        settings["user_call_name"] = input("你在光遇里的称呼/备注名（用于避免把备注当对话）: ").strip()
        save_settings(settings)

    if not settings.get("personality_prompt"):
        print("请输入性格提示词。比如：像真实朋友，大白话，别文艺，回复短一点。")
        settings["personality_prompt"] = input("性格提示词: ").strip()
        if not settings["personality_prompt"]:
            settings["personality_prompt"] = "像光遇里的真实朋友一样自然聊天，大白话，回复短一点。"
        save_settings(settings)

    return settings


def chat_url(base_url):
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def load_memory():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def add_memory(player_text, companion_text):
    memory = load_memory()
    memory.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "player": player_text[:120],
        "companion": companion_text[:120],
    })
    memory = memory[-200:]
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    return memory


def memory_prompt(memory, limit=12):
    if not memory:
        return "暂无长期记忆。"
    lines = []
    for item in memory[-limit:]:
        lines.append(f"- {item.get('time', '')} 玩家说：{item.get('player', '')}；你回：{item.get('companion', '')}")
    return "\n".join(lines)
