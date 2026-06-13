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
MEMORY_VERSION = 2
RAW_TURN_KEEP = 80
PENDING_TURN_KEEP = 30

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
        "model": "deepseek-v4-flash",
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


def _empty_memory():
    return {
        "version": MEMORY_VERSION,
        "profile_prompt": "",
        "profile_updated_at": "",
        "raw_turns": [],
        "pending_turns": [],
    }


def _normalize_turn(item):
    if not isinstance(item, dict):
        return None
    player = str(item.get("player", "") or "").strip()
    companion = str(item.get("companion", "") or "").strip()
    if not player and not companion:
        return None
    return {
        "time": str(item.get("time", "") or datetime.now().strftime("%Y-%m-%d %H:%M")),
        "player": player[:160],
        "companion": companion[:160],
    }


def _normalize_memory(data):
    memory = _empty_memory()
    if isinstance(data, list):
        turns = [_normalize_turn(item) for item in data]
        turns = [item for item in turns if item]
        memory["raw_turns"] = turns[-RAW_TURN_KEEP:]
        memory["pending_turns"] = turns[-PENDING_TURN_KEEP:]
        return memory
    if isinstance(data, dict):
        memory["profile_prompt"] = str(data.get("profile_prompt", "") or "").strip()
        memory["profile_updated_at"] = str(data.get("profile_updated_at", "") or "")
        raw_turns = [_normalize_turn(item) for item in data.get("raw_turns", [])]
        pending_turns = [_normalize_turn(item) for item in data.get("pending_turns", [])]
        memory["raw_turns"] = [item for item in raw_turns if item][-RAW_TURN_KEEP:]
        memory["pending_turns"] = [item for item in pending_turns if item][-PENDING_TURN_KEEP:]
    return memory


def save_memory(memory):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(_normalize_memory(memory), f, ensure_ascii=False, indent=2)


def load_memory():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        return _empty_memory()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            return _normalize_memory(data)
    except Exception:
        return _empty_memory()


def add_memory(player_text, companion_text):
    memory = load_memory()
    turn = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "player": player_text[:120],
        "companion": companion_text[:120],
    }
    memory["raw_turns"].append(turn)
    memory["pending_turns"].append(turn)
    memory["raw_turns"] = memory["raw_turns"][-RAW_TURN_KEEP:]
    memory["pending_turns"] = memory["pending_turns"][-PENDING_TURN_KEEP:]
    save_memory(memory)
    return memory


def memory_prompt(memory, limit=12):
    memory = _normalize_memory(memory)
    lines = []
    profile = memory.get("profile_prompt", "").strip()
    if profile:
        lines.append(profile)
    else:
        lines.append("暂无稳定长期理解。先按性格提示词自然聊天，不要假装知道没有确认过的事。")
    pending = memory.get("pending_turns", [])[-min(4, limit):]
    if pending:
        lines.append("\n最近还没整理进长期记忆的片段，仅作当前上下文参考：")
    for item in pending:
        lines.append(f"- {item.get('time', '')} 玩家说：{item.get('player', '')}；你回：{item.get('companion', '')}")
    return "\n".join(lines)


def memory_pending_turns(memory, limit=16):
    memory = _normalize_memory(memory)
    return memory.get("pending_turns", [])[-limit:]


def memory_recent_turns(memory, limit=80):
    memory = _normalize_memory(memory)
    return memory.get("raw_turns", [])[-limit:]


def memory_companion_replies(memory, limit=80):
    return [
        item.get("companion", "")
        for item in memory_recent_turns(memory, limit)
        if item.get("companion")
    ]


def memory_needs_update(memory, min_pending=6):
    memory = _normalize_memory(memory)
    pending = memory.get("pending_turns", [])
    if len(pending) >= min_pending:
        return True
    return bool(pending) and not memory.get("profile_prompt", "").strip()


def update_memory_profile(memory, profile_prompt):
    memory = _normalize_memory(memory)
    profile_prompt = str(profile_prompt or "").strip()
    if profile_prompt:
        memory["profile_prompt"] = profile_prompt[:1800]
        memory["profile_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        memory["pending_turns"] = []
        save_memory(memory)
    return memory
