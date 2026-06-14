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
QUICK_CONFIG_FILE = os.path.join(USER_DATA_DIR, "小懒快速配置.txt")
MEMORY_FILE = os.path.join(USER_DATA_DIR, "memory.json")
STYLE_KNOWLEDGE_FILE = os.path.join(USER_DATA_DIR, "style_knowledge.json")
SEARCH_KNOWLEDGE_FILE = os.path.join(USER_DATA_DIR, "search_knowledge.json")
MEMORY_VERSION = 2
RAW_TURN_KEEP = 80
PENDING_TURN_KEEP = 30
SEARCH_KNOWLEDGE_KEEP = 40

DEFAULT_SETTINGS = {
    "companion_name": "",
    "user_call_name": "",
    "require_user_recognition": None,
    "personality_prompt": "",
    "vision": {
        "provider": "local_ocr",
        "base_url": "",
        "model": "windows-ocr",
        "api_key": "",
    },
    "chat": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
        "api_key": "",
    },
    "web_search": {
        "enabled": True,
        "provider": "auto",
        "max_results": 3,
    },
    "vision_fallback": {
        "enabled": False,
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


def _yes_no(value, default=False):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text in ("y", "yes", "1", "true", "是", "需要", "开", "开启", "启用")


def _yes_no_text(value):
    return "是" if _yes_no(value, False) else "否"


def write_quick_config(settings):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    text = (
        "当前称呼：" + str(settings.get("companion_name", "") or "") + "\n\n"
        "使用者称呼：" + str(settings.get("user_call_name", "") or "") + "\n\n"
        "是否需要识别使用者：" + _yes_no_text(settings.get("require_user_recognition", False)) + "\n\n"
        "当前性格：\n" + str(settings.get("personality_prompt", "") or "").strip() + "\n"
    )
    with open(QUICK_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    return QUICK_CONFIG_FILE


def _field_before_next_label(text, label, following_labels):
    marker = label + "："
    if marker not in text:
        return None
    start = text.index(marker) + len(marker)
    end = len(text)
    for next_label in following_labels:
        next_marker = "\n" + next_label + "："
        pos = text.find(next_marker, start)
        if pos >= 0:
            end = min(end, pos)
    return text[start:end].strip()


def load_quick_config_values():
    if not os.path.exists(QUICK_CONFIG_FILE):
        return {}
    try:
        with open(QUICK_CONFIG_FILE, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except Exception:
        return {}
    labels = ["当前称呼", "使用者称呼", "是否需要识别使用者", "当前性格"]
    values = {}
    companion = _field_before_next_label(text, "当前称呼", labels[1:])
    user = _field_before_next_label(text, "使用者称呼", labels[2:])
    recog = _field_before_next_label(text, "是否需要识别使用者", labels[3:])
    personality = _field_before_next_label(text, "当前性格", [])
    if companion is not None:
        values["companion_name"] = companion.splitlines()[0].strip()
    if user is not None:
        values["user_call_name"] = user.splitlines()[0].strip()
    if recog is not None:
        values["require_user_recognition"] = _yes_no(recog, False)
    if personality is not None:
        values["personality_prompt"] = personality.strip()
    return values


def quick_config_mtime():
    try:
        return os.path.getmtime(QUICK_CONFIG_FILE)
    except OSError:
        return 0


def sync_quick_config(settings):
    settings = _deep_merge(DEFAULT_SETTINGS, settings)
    if os.path.exists(QUICK_CONFIG_FILE):
        values = load_quick_config_values()
        changed = False
        for key, value in values.items():
            if key in ("companion_name", "user_call_name", "personality_prompt") and value:
                if settings.get(key) != value:
                    settings[key] = value
                    changed = True
            elif key == "require_user_recognition":
                if bool(settings.get(key)) != bool(value):
                    settings[key] = bool(value)
                    changed = True
        if changed:
            save_settings(settings)
    else:
        write_quick_config(settings)
    return settings


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
    label = "可选视觉兜底模型"
    default_name = "视觉模型"
    if not is_vision:
        label = "聊天回复模型"
        default_name = "DeepSeek"

    current = settings[kind]
    if not is_vision:
        print("请填写 DeepSeek 聊天模型配置。")
        current["provider"] = "deepseek"
        current["base_url"] = _ask("DeepSeek 接口网址 base_url", current.get("base_url") or "https://api.deepseek.com")
        current["model"] = _ask("DeepSeek 模型名", current.get("model") or "deepseek-v4-pro")
        while not current.get("api_key"):
            current["api_key"] = _ask_secret("DeepSeek API Key")
            if not current["api_key"]:
                print("API Key 不能为空。")
        settings[kind] = current
        return

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
        current["provider"] = "custom_vision" if is_vision else "deepseek"
        current["base_url"] = _ask("接口网址 base_url", current["base_url"])
        current["model"] = _ask("模型名", current["model"])

    while not current.get("api_key"):
        current["api_key"] = _ask_secret(f"{label} API Key")
        if not current["api_key"]:
            print("API Key 不能为空。")
    settings[kind] = current


def ensure_settings():
    settings = load_settings()

    # 默认只用 Windows 本地 OCR 识别光遇文字，不强制要求额外视觉模型。
    # 视觉模型只作为高级兜底配置，用户手动打开 vision_fallback.enabled 时才会用到。
    if not settings.get("vision"):
        settings["vision"] = copy.deepcopy(DEFAULT_SETTINGS["vision"])
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

    if settings.get("require_user_recognition") is None:
        ans = input("是否需要识别使用者？需要输入 是，不需要输入 否 [是]: ").strip()
        settings["require_user_recognition"] = not ans or _yes_no(ans, True)
        save_settings(settings)

    settings = sync_quick_config(settings)
    write_quick_config(settings)
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


def load_style_knowledge():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(STYLE_KNOWLEDGE_FILE):
        return {}
    try:
        with open(STYLE_KNOWLEDGE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_style_knowledge(data):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    safe = {
        "version": 1,
        "prompt_key": str((data or {}).get("prompt_key", ""))[:80],
        "updated_at": str((data or {}).get("updated_at", "") or datetime.now().strftime("%Y-%m-%d %H:%M")),
        "style_prompt": str((data or {}).get("style_prompt", "") or "")[:1200],
    }
    with open(STYLE_KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2)
    return safe


def _safe_public_text(text, limit=600):
    text = str(text or "").strip()
    blocked = ("api key", "apikey", "sk-", "base_url", "http://", "https://")
    lines = []
    for line in text.splitlines():
        low = line.lower()
        if any(secret in low for secret in blocked):
            continue
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)[:limit]


def load_search_knowledge():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(SEARCH_KNOWLEDGE_FILE):
        return []
    try:
        with open(SEARCH_KNOWLEDGE_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        items = []
        for item in data:
            if not isinstance(item, dict):
                continue
            query = _safe_public_text(item.get("query", ""), 80)
            summary = _safe_public_text(item.get("summary", ""), 420)
            if query and summary:
                items.append({
                    "time": str(item.get("time", "") or ""),
                    "query": query,
                    "summary": summary,
                })
        return items[-SEARCH_KNOWLEDGE_KEEP:]
    except Exception:
        return []


def save_search_knowledge(items):
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    safe = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        query = _safe_public_text(item.get("query", ""), 80)
        summary = _safe_public_text(item.get("summary", ""), 420)
        if query and summary:
            safe.append({
                "time": str(item.get("time", "") or datetime.now().strftime("%Y-%m-%d %H:%M")),
                "query": query,
                "summary": summary,
            })
    safe = safe[-SEARCH_KNOWLEDGE_KEEP:]
    with open(SEARCH_KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2)
    return safe


def add_search_knowledge(query, summary):
    query = _safe_public_text(query, 80)
    summary = _safe_public_text(summary, 420)
    if not query or not summary or "搜索没有拿到可靠结果" in summary:
        return load_search_knowledge()
    items = load_search_knowledge()
    key = "".join(ch for ch in query.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    kept = []
    for item in items:
        old_key = "".join(ch for ch in item.get("query", "").lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        if old_key != key:
            kept.append(item)
    kept.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "query": query,
        "summary": summary,
    })
    return save_search_knowledge(kept)


def search_knowledge_prompt(items, current_text="", limit=3):
    items = load_search_knowledge() if items is None else list(items or [])
    if not items:
        return ""
    current = str(current_text or "")
    current_chars = set(ch for ch in current if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    ranked = []
    for item in items:
        hay = str(item.get("query", "") + item.get("summary", ""))
        hay_chars = set(ch for ch in hay if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        score = len(current_chars & hay_chars)
        ranked.append((score, item))
    ranked.sort(key=lambda x: x[0], reverse=True)
    selected = [item for score, item in ranked if score >= 2][:limit]
    if not selected:
        selected = [item for _, item in ranked[:1]]
    lines = []
    for item in selected:
        lines.append("- " + item.get("query", "") + "：" + item.get("summary", "").replace("\n", " / "))
    return "\n".join(lines)


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
