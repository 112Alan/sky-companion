# -*- coding: utf-8 -*-
"""Sky Companion - screenshot OCR chat agent."""
import sys, os, time, re, base64, io, json, subprocess, difflib, requests, numpy as np
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.screen_capture import capture_window, sky_window_foreground, window_exists
from core.game_controller import activate_sky_window, GameController
from core.user_settings import (
  add_memory,
  chat_url,
  ensure_settings,
  load_memory,
  memory_companion_replies,
  memory_needs_update,
  memory_pending_turns,
  memory_prompt,
  update_memory_profile,
)
from openai import OpenAI

ctrl = GameController()

APP_DIR = Path(__file__).resolve().parents[1]
LOCAL_OCR_SCRIPT = APP_DIR / "windows_ocr.ps1"
LOCAL_OCR_IMAGE = APP_DIR / "outputs" / "ocr_latest.jpg"
LOCAL_OCR_TIMEOUT = 3
VISION_TIMEOUT = 8
VISION_FALLBACK_INTERVAL = 8.0
VISION_FALLBACK_ON_EMPTY = False

VISION_PROMPT = """You are reading a Sky: Children of the Light screenshot.
Extract only player chat text from chat bubbles or the opened chat history.
Ignore system toasts, event notices, menus, buttons, shortcut letters, sleep Z marks, player names, remarks, scenery text, and UI labels.
Do not return season/event notices such as 狂欢季的新任务现已开启.
Return one chat message per line, with no JSON, speaker labels, explanations, or quotes.
If there is no clear player chat message, return EMPTY."""

SELF_ECHO_SILENCE = 2.0
SELF_ECHO_WINDOW = 30.0
OCR_MIN_INTERVAL = 0.6
ECHO_BACKOFF = 2.0
MSG_STABLE_SECONDS = 1.15
ELLIPSIS_STABLE_SECONDS = 2.2
REPLY_COOLDOWN = 1.2
CHANGE_THRESHOLD = 10
DEFAULT_IGNORE_REMARKS = ["大号", "小号", "好友", "备注", "主人"]
OCR_GARBAGE_CHARS = set("卩厶艹丶丿丨亅乀乁乛冫冖冂亠乚龴彡彳灬攵犭礻衤讠钅阝饣忄扌氵殄咿忡吣吢杓唥竄孓")
TOPIC_ONLY_WORDS = set(["跑图", "任务", "做任务", "狂欢", "狂欢季", "编钟"])
UI_TEXT_HINTS = [
  "狂欢", "狂欢季", "季节", "先祖", "编钟", "任务", "活动", "礼包", "商店", "蜡烛",
  "爱心", "斗篷", "发型", "面具", "乐器", "兑换", "领取", "剩余", "点击",
  "好友解除", "已经与此好友解除", "现已开启", "新任务", "设置", "确定", "取消",
]
UI_EXACT_TEXTS = ["光遇", "号", "现", "现在", "狂", "造", "故", "接", "看", "没", "设", "君", "Z", "z"]
CHAT_HINTS = [
  "你好", "哈喽", "嗨", "早上好", "晚上好", "晚安", "在吗", "走", "来", "去",
  "你", "我", "咱", "我们", "怎么", "为什么", "什么", "哪", "喊", "吗", "呢",
  "谁", "咋", "干嘛", "会什么", "不去", "说话", "回话", "理我", "不说话", "哑巴",
  "别", "服", "烦", "笑死", "好笑", "人机", "真人", "禁言", "讲人话", "转人工",
  "草", "靠", "无语", "救命", "行", "好",
  "？", "?", "！", "!",
]
STRONG_CHAT_HINTS = [
  "你好", "哈喽", "嗨", "早上好", "晚上好", "晚安", "在吗", "你在吗",
  "走啊", "来吗", "去吗", "去不去", "做任务", "跑图", "说话", "回话",
  "理我", "不说话", "哑巴", "你是谁", "你在干嘛", "你会什么",
  "我服", "笑死", "无语", "救命", "怎么", "为什么", "干嘛", "什么",
  "好笑", "好好笑", "人机", "真人", "禁言", "讲人话", "转人工", "转人", "带我",
  "？", "?", "！", "!",
]
MUST_REPLY_HINTS = [
  "你是谁", "你在吗", "在不在", "说话", "回话", "理我", "不说话", "哑巴",
  "你在干嘛", "你会什么", "为什么", "怎么不", "扫描错", "识别错", "看错",
]
NON_CHAT_SUBSTRINGS = [
  "PowerShell", "Python", "PID", "github", "GitHub", "Codex", "codex",
  "管理员", "接管", "日志", "程序", "当前在跑", "启动成功", "测试接管",
  "选择", "PressEnter", "baseurl", "model", "apikey", "key", "OCR",
  "Start", "Ready", "timeout", "http", "https", "url", "v1chatcompletions",
  "模型", "接口", "配置", "版本", "视觉", "本地", "DeepSeek", "Gemini",
  "回复一条", "这一套", "GitHub", "截图", "识别", "中转站",
  "同步", "密钥", "扫描", "工作副本", "提交", "推到", "视频", "开发", "桌宠", "分析",
]

class SkyCompanionAgent:
  def __init__(self, settings=None):
    self.settings = settings or ensure_settings()
    if not self.settings:
      raise SystemExit(1)
    self.companion_name = self.settings["companion_name"]
    self.user_call_name = self.settings.get("user_call_name", "")
    self.personality_prompt = self.settings.get("personality_prompt", "")
    self.vision = self.settings["vision"]
    self.chat = self.settings["chat"]
    self.dclient = OpenAI(api_key=self.chat["api_key"], base_url=self.chat["base_url"])
    self.memory = load_memory()
    self.my_words = []; self.last_time = 0
    self.prev = None; self.last_text = ""
    self.seen = []; self.last_text = ""
    self.last_sent_text = ""
    self.last_sent_at = 0
    self.next_ocr_at = 0
    self.echo_backoff_until = 0
    self.last_ignored_text = ""
    self.pending_msg = ""
    self.pending_since = 0
    self.candidate_msg = ""
    self.candidate_since = 0
    self.candidate_seen_at = 0
    self.last_empty_ocr_log = 0
    self.empty_ocr_count = 0
    self.replied_msgs = []
    self.ignored_msgs = []
    self.scanned_msgs = []
    self.dialogue_turns = []
    self.last_vision_fallback_at = time.time()
    self.last_local_ocr_error_at = 0
    self.memory_updating = False
    self.last_not_foreground_log = 0

  def _log(self, m): print(f"[{time.strftime('%H:%M:%S')}] {m}")

  def _same(self, a, b):
    """判断两条文字是否相似（忽略标点）"""
    import re
    ca = set(re.findall(r"[\u4e00-\u9fff]", a or ""))
    cb = set(re.findall(r"[\u4e00-\u9fff]", b or ""))
    if not ca or not cb: return False
    overlap = len(ca & cb)
    return overlap / max(len(ca), len(cb)) > 0.5

  def _clean_text(self, txt):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", txt or "").strip()

  def _norm_ocr_key(self, txt):
    txt = self._clean_text(txt)
    table = str.maketrans({
      "訁": "言",
      "讠": "言",
      "門": "门",
      "冂": "门",
      "卩": "",
      "厶": "",
      "丶": "",
      "丿": "",
      "丨": "",
    })
    return txt.translate(table)

  def _has_ellipsis_tail(self, txt):
    return bool(re.search(r"(\.{2,}|…+|。{2,}|[，,、·丶]{2,})\s*$", str(txt or "")))

  def _has_chat_intent(self, txt):
    clean = self._clean_text(txt)
    if len(clean) < 2:
      return False
    if clean in TOPIC_ONLY_WORDS:
      return False
    if self._looks_like_ocr_garbage(txt):
      return False
    if any(h in txt or h in clean for h in STRONG_CHAT_HINTS):
      return True
    if len(clean) <= 4:
      return False
    weak = [h for h in CHAT_HINTS if h not in ("你", "我", "好", "来", "去", "行")]
    if any(h in txt or h in clean for h in weak):
      return True
    return len(clean) >= 6

  def _must_reply(self, txt):
    clean = self._clean_text(txt)
    return any(h in txt or h in clean for h in MUST_REPLY_HINTS)

  def _fallback_reply(self, txt):
    clean = self._clean_text(txt)
    if "你是谁" in clean:
      return "我是小懒呀。"
    if "扫描错" in clean or "识别错" in clean or "看错" in clean:
      return "可能看岔了，我再瞅瞅。"
    if "在吗" in clean or "在不在" in clean:
      return "在呢在呢。"
    if "说话" in clean or "回话" in clean or "理我" in clean or "哑巴" in clean:
      return "来了来了，刚卡了一下。"
    if "为什么" in clean:
      return "可能刚刚卡了。"
    if "你会什么" in clean:
      return "聊天跑图都能陪你。"
    if "你在干嘛" in clean:
      return "等你发话呢。"
    return ""

  def _is_noise_text(self, txt):
    clean = self._clean_text(txt)
    if not clean:
      return True
    if clean in UI_EXACT_TEXTS:
      return True
    if clean.lower() in ("z", "zz", "zzz"):
      return True
    if len(clean) <= 1:
      return True
    if any(h in clean for h in CHAT_HINTS):
      return False
    if any(h in clean for h in UI_TEXT_HINTS):
      return True
    if "任务" in clean and "开启" in clean:
      return True
    return False

  def _looks_like_non_chat_line(self, txt):
    raw = str(txt or "").strip()
    clean = self._clean_text(raw)
    if not clean:
      return True
    compact_clean = clean.lower()
    for word in NON_CHAT_SUBSTRINGS:
      key = self._clean_text(word).lower()
      if word in raw or (key and key in compact_clean):
        return True
    if re.search(r"\b(pid|python|powershell|log|http|https)\b", raw, re.I):
      return True
    if len(clean) >= 18 and not self._has_chat_intent(raw):
      return True
    return False

  def _looks_like_ocr_garbage(self, txt):
    raw = str(txt or "")
    clean = self._clean_text(raw)
    if not clean:
      return True
    zh = re.findall(r"[\u4e00-\u9fff]", clean)
    digits = re.findall(r"\d", clean)
    letters = re.findall(r"[A-Za-z]", clean)
    symbols = re.findall(r"[^\w\s\u4e00-\u9fff]", raw)
    garbage_chars = [ch for ch in clean if ch in OCR_GARBAGE_CHARS]
    strong = any(h in raw or h in clean for h in STRONG_CHAT_HINTS)
    if not zh:
      return True
    if self._has_ellipsis_tail(raw):
      return True
    if clean in TOPIC_ONLY_WORDS:
      return True
    if "吗" in clean and len(zh) >= 2:
      return False
    if len(zh) <= 1 and (len(clean) <= 3 or len(digits) >= 1):
      return True
    if len(digits) >= 2 and len(zh) <= 2:
      return True
    if re.search(r"[0oO@]{2,}", clean) and len(zh) <= 2:
      return True
    if not strong:
      if re.search(r"^[。．、·丶'\"“”‘’`]+", raw.strip()):
        return True
      if re.search(r"[一二三四五六七八九十]{2,}", clean):
        return True
      if len(garbage_chars) >= 2:
        return True
      if garbage_chars and (digits or letters or symbols or len(clean) <= 4):
        return True
      if (digits or letters) and len(zh) <= 4:
        return True
      if symbols and len(symbols) >= 2 and len(zh) <= 6:
        return True
      if len(clean) >= 6 and (digits or letters or len(garbage_chars) >= 1):
        return True
    return False

  def _contains_clean(self, a, b, min_len=2):
    ca = self._clean_text(a)
    cb = self._clean_text(b)
    if len(ca) < min_len or len(cb) < min_len:
      return False
    return ca in cb or cb in ca

  def _echo_key(self, txt):
    clean = self._clean_text(txt)
    for name in self._ignore_remarks():
      n = self._clean_text(name)
      if n:
        clean = clean.replace(n, "")
    clean = re.sub(r"^[0oO]+", "", clean)
    return clean

  def _same_own_reply(self, txt, own, memory=False):
    a = self._echo_key(txt)
    b = self._echo_key(own)
    if len(a) < 2 or len(b) < 2:
      return False
    if a == b:
      return True
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
      return True
    if memory and min(len(a), len(b)) < 5:
      return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    sa = set(re.findall(r"[\u4e00-\u9fff]", a))
    sb = set(re.findall(r"[\u4e00-\u9fff]", b))
    overlap = len(sa & sb) / max(1, min(len(sa), len(sb)))
    if memory:
      return ratio >= 0.72 or (ratio >= 0.58 and overlap >= 0.80)
    return ratio >= 0.58 or overlap >= 0.70

  def _ignore_remarks(self):
    names = [self.companion_name, self.user_call_name] + DEFAULT_IGNORE_REMARKS
    return [n for n in names if n]

  def _is_remark_or_name(self, txt):
    """过滤光遇头顶名称、好友备注、OCR截断的名字。"""
    clean = self._clean_text(txt)
    if not clean:
      return True
    for name in self._ignore_remarks():
      n = self._clean_text(name)
      if clean == n:
        return True
      if len(clean) <= len(n) and len(clean) >= 2 and (clean in n or n in clean):
        return True
    name_words = ["大号", "小号", "备注", "好友", "主人"]
    if len(clean) <= 6 and any(w in clean for w in name_words):
      return True
    return False

  def _parse_vision_text(self, txt):
    """把视觉输出整理成多行白色文字列表。"""
    txt = (txt or "").strip()
    if not txt or txt.upper() == "EMPTY":
      return ""
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.I | re.S).strip()

    try:
      data = json.loads(txt)
      if isinstance(data, dict):
        values = []
        for key in ("texts", "items", "lines", "message", "text"):
          value = data.get(key)
          if isinstance(value, list):
            values.extend(str(v) for v in value)
          elif isinstance(value, str):
            values.append(value)
        txt = "\n".join(values)
      elif isinstance(data, list):
        txt = "\n".join(str(v) for v in data)
    except Exception:
      pass
    lines = []
    seen = set()
    for line in txt.split("\n"):
      line = re.sub(r"^\s*[-*•\d.、]+", "", line).strip()
      line = line.strip("\"'“”‘’")
      if not re.search(r"[\u4e00-\u9fff]", line):
        continue
      clean = self._clean_text(line)
      if self._is_noise_text(clean):
        continue
      if self._looks_like_non_chat_line(line):
        continue
      if self._looks_like_ocr_garbage(line):
        continue
      if not clean or clean in seen:
        continue
      seen.add(clean)
      lines.append(line)
      if len(lines) >= 12:
        break
    return "\n".join(lines).strip()

  def _is_self_echo(self, txt):
    """判断OCR内容是不是自己刚发出去的话。"""
    if not txt:
      return False
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    if len(lines) > 1:
      return all(self._is_self_echo(line) or self._is_remark_or_name(line) for line in lines)
    if self.last_sent_text and time.time() - self.last_sent_at < SELF_ECHO_WINDOW:
      if self._same_own_reply(txt, self.last_sent_text):
        return True
      if self._same(txt, self.last_sent_text):
        return True
      clean_new = self._clean_text(txt)
      clean_self = self._clean_text(self.last_sent_text)
      if clean_new and clean_self and (clean_new in clean_self or clean_self in clean_new):
        return True
    for w in self.my_words[-4:]:
      if w and (self._same_own_reply(txt, w) or self._same(txt, w) or self._contains_clean(txt, w)):
        return True
    for old_reply in memory_companion_replies(self.memory, 80):
      if old_reply and self._same_own_reply(txt, old_reply, memory=True):
        return True
    return False

  def _hold_candidate(self, txt):
    """等OCR结果稳定，避免把半句话直接拿去回复。"""
    now = time.time()
    clean = self._clean_text(txt)
    if not clean:
      return
    if self.candidate_msg and self._contains_clean(txt, self.candidate_msg):
      old = self._clean_text(self.candidate_msg)
      if len(clean) > len(old):
        self.candidate_msg = txt
        self.candidate_since = now
      self.candidate_seen_at = now
      return
    self.candidate_msg = txt
    self.candidate_since = now
    self.candidate_seen_at = now
    self._log("Read: " + txt[:60])

  def _take_stable_candidate(self):
    if not self.candidate_msg:
      return ""
    wait_seconds = ELLIPSIS_STABLE_SECONDS if self._has_ellipsis_tail(self.candidate_msg) else MSG_STABLE_SECONDS
    if time.time() - self.candidate_since < wait_seconds:
      return ""
    msg = self.candidate_msg
    self.candidate_msg = ""
    self.candidate_since = 0
    self.candidate_seen_at = 0
    return msg

  def _should_reply(self, txt):
    """回复闸门：不确定是玩家在说话时宁可不回。"""
    txt = self._parse_vision_text(txt)
    clean = self._clean_text(txt)
    if len(clean) < 2:
      return False
    if self._looks_incomplete(txt):
      return False
    if self._looks_like_ui_text(txt):
      return False
    if self._is_remark_or_name(txt):
      return False
    if self._is_self_echo(txt):
      return False
    ui_words = ["确定", "取消", "设置", "返回", "跳过", "领取", "商店", "好友", "任务", "邀请", "服务器", "连接"]
    if clean in ui_words:
      return False
    return True

  def _looks_incomplete(self, txt):
    clean = self._clean_text(txt)
    if not clean:
      return True
    if self._has_ellipsis_tail(txt):
      return True
    if clean in TOPIC_ONLY_WORDS:
      return True
    if len(clean) <= 6 and clean[-1] in "的在把被给和跟又该新":
      return True
    if clean in ("什么", "怎么", "你该", "怎么又"):
      return True
    return False

  def _looks_like_ui_text(self, txt):
    clean = self._clean_text(txt)
    if not clean:
      return True
    if clean in UI_EXACT_TEXTS:
      return True
    if self._is_noise_text(clean) and not any(h in txt for h in CHAT_HINTS):
      return True
    if len(clean) <= 3 and (clean.startswith("现在") or clean.startswith("狂")):
      return True
    has_chat_hint = any(h in txt for h in CHAT_HINTS)
    for hint in UI_TEXT_HINTS:
      if hint in clean and not has_chat_hint:
        return True
    return False

  def _looks_like_chat(self, txt):
    clean = self._clean_text(txt)
    if len(clean) < 2:
      return False
    if self._has_chat_intent(txt):
      return True
    # 稍长的句子没有明显UI词时，先当作可能的人话。
    return len(clean) >= 7

  def _select_player_message(self, txt):
    """从OCR多行里只取最像玩家最新发言的一句，避免把整屏说明文字丢给模型。"""
    lines = []
    for line in (txt or "").split("\n"):
      line = line.strip()
      if not line:
        continue
      clean = self._clean_text(line)
      if not clean:
        continue
      if self._is_remark_or_name(line) or self._is_self_echo(line):
        continue
      if self._is_noise_text(line) or self._looks_like_non_chat_line(line):
        continue
      if self._looks_like_ocr_garbage(line):
        continue
      if len(clean) <= 2 and not self._has_chat_intent(line):
        continue
      lines.append(line)
    if not lines:
      return ""
    chat_lines = [line for line in lines if self._has_chat_intent(line)]
    if chat_lines:
      return chat_lines[-1]
    if len(lines) > 1:
      return ""
    clean = self._clean_text(lines[0])
    if len(clean) < 7 and not self._has_chat_intent(lines[0]):
      return ""
    return lines[0]

  def _recent_dialogue_prompt(self):
    if not self.dialogue_turns:
      return "暂无。"
    lines = []
    for item in self.dialogue_turns[-8:]:
      lines.append("玩家：" + item.get("player", ""))
      reply = item.get("reply", "")
      lines.append(self.companion_name + "：" + (reply if reply else "（没有回复）"))
    return "\n".join(lines)

  def _filter_screen_text(self, txt):
    """去掉明显UI行，保留可能是玩家说话的白字。"""
    kept = []
    for line in (txt or "").split("\n"):
      line = line.strip()
      if not line:
        continue
      clean = self._clean_text(line)
      if not clean:
        continue
      if self._is_remark_or_name(line):
        continue
      if self._is_self_echo(line):
        continue
      if self._looks_like_ui_text(line) and not self._looks_like_chat(line):
        continue
      if self._looks_like_ocr_garbage(line):
        continue
      kept.append(line)
    return "\n".join(kept)

  def _is_known_line(self, line):
    key = self._conversation_key(line)
    if not key:
      return True
    now = time.time()
    self.replied_msgs = [(old, ts) for old, ts in self.replied_msgs if now - ts < 45]
    self.ignored_msgs = [(old, ts) for old, ts in self.ignored_msgs if now - ts < 25]
    self.scanned_msgs = [(old, ts) for old, ts in self.scanned_msgs if now - ts < 18]
    for pool in (self.replied_msgs, self.ignored_msgs, self.scanned_msgs):
      for old, ts in pool:
        if self._similar_key(key, old):
          return True
    return False

  def _fresh_screen_text(self, txt):
    """只保留当前白字列表里还没处理过的新行。"""
    fresh = []
    for line in self._filter_screen_text(txt).split("\n"):
      line = line.strip()
      if not line:
        continue
      if self._is_known_line(line):
        continue
      fresh.append(line)
    return self._select_player_message("\n".join(fresh))

  def _conversation_key(self, txt):
    filtered = self._filter_screen_text(txt)
    lines = [self._clean_text(l) for l in filtered.split("\n") if self._clean_text(l)]
    if lines:
      best = max(lines, key=len)
    else:
      best = self._clean_text(txt)
    for name in self._ignore_remarks():
      n = self._clean_text(name)
      if n:
        best = best.replace(n, "")
    best = re.sub(r"^(吖|啊|呀|哎|诶|喂)+", "", best)
    for greet in ("你好", "哈喽", "嗨", "晚上好", "早上好", "晚安"):
      if greet in best and len(best) <= len(greet) + 3:
        best = greet
        break
    return re.sub(r"(吗|呢|啊|呀|吧|嘛|哈)+$", "", best)

  def _is_too_fragmentary(self, txt):
    filtered = self._filter_screen_text(txt)
    lines = [self._clean_text(l) for l in filtered.split("\n") if self._clean_text(l)]
    if not lines:
      return True
    if len(lines) == 1:
      clean = lines[0]
      if len(clean) <= 1:
        return True
      if clean in ("你", "我", "他", "她", "它", "们", "我们", "你们", "现在"):
        return True
    if len(lines) > 1:
      total = sum(len(line) for line in lines)
      if all(len(line) <= 1 for line in lines):
        return True
      if total <= 4 and not any(h in filtered for h in STRONG_CHAT_HINTS):
        return True
    return False

  def _similar_key(self, a, b):
    a = self._norm_ocr_key(a)
    b = self._norm_ocr_key(b)
    if not a or not b:
      return False
    if a == b:
      return True
    if len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
      return True
    for greet in ("你好", "哈喽", "晚上好", "早上好", "晚安"):
      if greet in a and greet in b and min(len(a), len(b)) <= len(greet) + 3:
        return True
    sa = set(re.findall(r"[\u4e00-\u9fff]", a))
    sb = set(re.findall(r"[\u4e00-\u9fff]", b))
    if not sa or not sb:
      return False
    overlap = len(sa & sb) / max(len(sa), len(sb))
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio >= 0.68 and overlap >= 0.60 and abs(len(a) - len(b)) <= 4:
      return True
    common_prefix = 0
    for ca, cb in zip(a, b):
      if ca != cb:
        break
      common_prefix += 1
    if common_prefix >= 2 and ratio >= 0.54 and overlap >= 0.50 and abs(len(a) - len(b)) <= 5:
      return True
    return overlap >= 0.75 and abs(len(a) - len(b)) <= 3

  def _scanned_recently(self, txt):
    key = self._conversation_key(txt)
    if not key:
      return True
    now = time.time()
    self.scanned_msgs = [(old, ts) for old, ts in self.scanned_msgs if now - ts < 18]
    for old, ts in self.scanned_msgs:
      if self._similar_key(key, old):
        return True
    return False

  def _mark_scanned(self, txt):
    key = self._conversation_key(txt)
    if not key:
      return
    self.scanned_msgs.append((key, time.time()))
    if len(self.scanned_msgs) > 40:
      self.scanned_msgs = self.scanned_msgs[-40:]

  def _remember_turn(self, player, reply=""):
    if not player:
      return
    self.dialogue_turns.append({"player": player[:80], "reply": reply[:80]})
    if len(self.dialogue_turns) > 20:
      self.dialogue_turns = self.dialogue_turns[-20:]

  def _ignored_recently(self, txt):
    clean = self._conversation_key(txt)
    if not clean:
      return True
    is_block = "\n" in (txt or "")
    now = time.time()
    self.ignored_msgs = [(old, ts) for old, ts in self.ignored_msgs if now - ts < 25]
    for old, ts in self.ignored_msgs:
      old_clean = self._clean_text(old)
      if self._similar_key(clean, old_clean):
        return True
    return False

  def _changed(self, shot):
    arr = np.array(shot)
    if self.prev is not None and arr.shape == self.prev.shape:
      diff = np.mean(np.abs(arr - self.prev))
      self.prev = arr.copy()
      return diff > CHANGE_THRESHOLD
    self.prev = arr.copy(); return True

  def _vision_prompt(self):
    recent = " | ".join([w for w in self.my_words[-4:] if w])
    remarks = " | ".join(self._ignore_remarks())
    return VISION_PROMPT + "\nNever return these own/remark texts: " + recent + " | " + remarks

  def _normalize_local_ocr_line(self, line):
    return re.sub(r"\s+", "", str(line or "")).strip()

  def _make_region(self, w, h, ratios):
    left = max(0, min(w - 1, int(w * ratios[0])))
    top = max(0, min(h - 1, int(h * ratios[1])))
    right = max(left + 1, min(w, int(w * ratios[2])))
    bottom = max(top + 1, min(h, int(h * ratios[3])))
    return left, top, right, bottom

  def _local_ocr_regions(self, image):
    w, h = image.size
    return [
      self._make_region(w, h, (0.02, 0.10, 0.78, 0.86)),
      self._make_region(w, h, (0.12, 0.08, 0.96, 0.80)),
    ]

  def _enhance_local_ocr_crop(self, crop):
    crop = crop.convert("RGB")
    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    scale = 2 if max(crop.size) < 1400 else 1
    if scale > 1:
      crop = crop.resize((crop.width * scale, crop.height * scale), resampling)
    gray = ImageOps.grayscale(crop)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.55)
    gray = gray.filter(ImageFilter.SHARPEN)
    return Image.merge("RGB", (gray, gray, gray))

  def _save_local_ocr_target(self, image):
    LOCAL_OCR_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    crops = [self._enhance_local_ocr_crop(image.crop(region)) for region in self._local_ocr_regions(image)]
    gap = 12
    width = max(crop.width for crop in crops)
    height = sum(crop.height for crop in crops) + gap * (len(crops) - 1)
    canvas = Image.new("RGB", (width, height), "black")
    y = 0
    for crop in crops:
      canvas.paste(crop, (0, y))
      y += crop.height + gap
    canvas.save(LOCAL_OCR_IMAGE, format="JPEG", quality=86, optimize=True)
    return str(LOCAL_OCR_IMAGE)

  def _do_local_ocr(self, shot):
    if not LOCAL_OCR_SCRIPT.exists():
      return {"available": False, "text": "", "raw_lines": [], "error": "missing windows_ocr.ps1"}
    try:
      target = self._save_local_ocr_target(shot)
      creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
      completed = subprocess.run(
        [
          "powershell.exe",
          "-NoProfile",
          "-ExecutionPolicy",
          "Bypass",
          "-File",
          str(LOCAL_OCR_SCRIPT),
          target,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=LOCAL_OCR_TIMEOUT,
        creationflags=creationflags,
      )
      if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or "").strip()
        return {"available": False, "text": "", "raw_lines": [], "error": error[-160:]}
      raw_output = (completed.stdout or "{}").strip()
      if not raw_output.startswith("{"):
        raw_output = base64.b64decode(raw_output).decode("utf-8")
      payload = json.loads(raw_output)
      if "line_codes" in payload:
        raw_lines = [
          self._normalize_local_ocr_line("".join(chr(int(code)) for code in line_codes))
          for line_codes in payload.get("line_codes", [])
        ]
      else:
        raw_lines = [self._normalize_local_ocr_line(line) for line in payload.get("lines", [])]
      raw_lines = [line for line in raw_lines if line]
      text = self._parse_vision_text("\n".join(raw_lines))
      return {"available": True, "text": text, "raw_lines": raw_lines, "error": ""}
    except Exception as e:
      return {"available": False, "text": "", "raw_lines": [], "error": str(e)[:160]}

  def _do_vision_ocr(self, shot):
    """Gemini识图兜底。"""
    max_side = 900
    if max(shot.size) > max_side:
      scale = max_side / max(shot.size)
      shot = shot.resize((max(1, int(shot.width * scale)), max(1, int(shot.height * scale))))
    buf = io.BytesIO(); shot.save(buf, format="JPEG", quality=70)
    b64 = base64.b64encode(buf.getvalue()).decode()
    try:
      r = requests.post(chat_url(self.vision["base_url"]),
        headers={"Authorization":"Bearer " + self.vision["api_key"],"Content-Type":"application/json"},
        json={"model":self.vision["model"],"messages":[{"role":"user","content":[
          {"type":"text","text":self._vision_prompt()},
          {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64}}
        ]}],"max_tokens":220},
        timeout=VISION_TIMEOUT)
      if r.status_code != 200:
        self._log("VHTTP: " + str(r.status_code) + " " + r.text[:80].replace("\n", " "))
        return ""
      data = r.json()
      t = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
      if t.upper() == "EMPTY":
        return ""
      if t:
        t = self._parse_vision_text(t)
        if t: return t
    except Exception as e:
      self._log("V: " + str(e)[:60])
    return ""

  def _do_ocr(self, shot=None):
    """先用本地OCR快扫；必要时才用Gemini兜底。"""
    shot = shot or capture_window()
    if not shot: return ""
    local = self._do_local_ocr(shot)
    if local.get("available"):
      text = local.get("text", "")
      if text:
        return text
      # 本地OCR看到了字但都被判成系统/UI，直接跳过，避免每帧都卡视觉模型。
      if local.get("raw_lines"):
        return ""
      if not VISION_FALLBACK_ON_EMPTY:
        return ""
      # 完全没扫到字时，偶尔用Gemini兜底一次。
      if time.time() - self.last_vision_fallback_at < VISION_FALLBACK_INTERVAL:
        return ""
      self.last_vision_fallback_at = time.time()
      self._log("OCR: local empty, Gemini fallback")
      return self._do_vision_ocr(shot)

    if time.time() - self.last_local_ocr_error_at > 10:
      self._log("LOCR: " + str(local.get("error", "unavailable"))[:80])
      self.last_local_ocr_error_at = time.time()
    self.last_vision_fallback_at = time.time()
    return self._do_vision_ocr(shot)

  def _news(self, old, new):
    """找出新文字（在new中但不在old中）"""
    if not new: return ""
    if not old: return new
    olds = set(line.strip() for line in old.split("\n") if line.strip())
    news = [line.strip() for line in new.split("\n") if line.strip()]
    diff = [l for l in news if l not in olds]
    return "\n".join(diff) if diff else ""

  def _seen_recently(self, txt):
    clean = self._conversation_key(txt)
    if not clean:
      return True
    is_block = "\n" in (txt or "")
    now = time.time()
    self.replied_msgs = [(old, ts) for old, ts in self.replied_msgs if now - ts < 45]
    for old, ts in self.replied_msgs:
      old_clean = self._clean_text(old)
      if not old_clean:
        continue
      if self._similar_key(clean, old_clean):
        return True
    return False

  def _mark_seen(self, txt, replied=True):
    if not txt:
      return
    key = self._conversation_key(txt)
    self.seen.append(key)
    if replied:
      self.replied_msgs.append((key, time.time()))
    else:
      self.ignored_msgs.append((key, time.time()))
    self._mark_scanned(key)
    if len(self.seen) > 50:
      self.seen = self.seen[-50:]
    if len(self.replied_msgs) > 30:
      self.replied_msgs = self.replied_msgs[-30:]
    if len(self.ignored_msgs) > 30:
      self.ignored_msgs = self.ignored_msgs[-30:]

  def _send_reply(self, new_msg):
    """对一条确认过的玩家新消息生成回复并打进游戏。"""
    filtered_msg = self._select_player_message(self._filter_screen_text(new_msg))
    if not filtered_msg or self._is_too_fragmentary(filtered_msg):
      self._log("Skip: " + new_msg.replace("\n", " | ")[:80])
      self._mark_seen(new_msg, replied=False)
      return False
    if not self._should_reply(filtered_msg):
      self._log("Skip: " + filtered_msg.replace("\n", " | ")[:80])
      self._mark_seen(filtered_msg, replied=False)
      return False
    self._log("New: " + filtered_msg.replace("\n", " | ")[:80])

    reply = self._ch(filtered_msg)
    if not reply and self._must_reply(filtered_msg):
      reply = self._fallback_reply(filtered_msg)
    self._log("DS: " + (reply[:50] if reply else "empty"))
    if not reply:
      self._log("Decide: no reply")
      self._mark_seen(filtered_msg, replied=False)
      self._remember_turn(filtered_msg, "")
      return False
    reply = reply.strip().strip("\"\'")
    if len(reply) < 2:
      return False

    self._log("Say: " + reply[:50])
    activate_sky_window(); time.sleep(0.3)
    ctrl.send_chat_message(reply[:60])
    self.my_words.append(reply)
    self.last_sent_text = reply
    self.last_sent_at = time.time()
    self._mark_seen(filtered_msg, replied=True)
    self.memory = add_memory(filtered_msg, reply)
    self._remember_turn(filtered_msg, reply)
    if len(self.my_words) > 8: self.my_words.pop(0)
    self.last_time = time.time()
    self.skip = 3
    time.sleep(0.3)
    self._maybe_update_memory()
    return True

  def _chat_extra_body(self):
    model = str(self.chat.get("model", "")).lower()
    base = str(self.chat.get("base_url", "")).lower()
    if "deepseek" in model or "deepseek" in base:
      return {"thinking": {"type": "disabled"}}
    return None

  def _chat_completion(self, prompt, temperature=0.9, max_tokens=60):
    kwargs = {
      "model": self.chat["model"],
      "messages": [{"role": "user", "content": prompt}],
      "temperature": temperature,
      "max_tokens": max_tokens,
    }
    extra_body = self._chat_extra_body()
    if extra_body:
      kwargs["extra_body"] = extra_body
    return self.dclient.chat.completions.create(**kwargs)

  def _clean_memory_summary(self, txt):
    txt = (txt or "").strip()
    txt = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", txt, flags=re.I | re.S).strip()
    txt = txt.replace("长期记忆：", "").strip()
    lines = []
    for line in txt.splitlines():
      line = line.strip()
      if not line:
        continue
      if any(secret in line.lower() for secret in ("api key", "apikey", "sk-", "base_url", "http://", "https://")):
        continue
      lines.append(line)
    return "\n".join(lines).strip()

  def _maybe_update_memory(self, force=False):
    if self.memory_updating:
      return
    if not force and not memory_needs_update(self.memory, min_pending=6):
      return
    pending = memory_pending_turns(self.memory, limit=16)
    if not pending:
      return
    self.memory_updating = True
    try:
      transcript = []
      for item in pending:
        player = item.get("player", "").replace("\n", " / ")
        companion = item.get("companion", "").replace("\n", " / ")
        transcript.append(f"{item.get('time', '')} 玩家：{player}\n{self.companion_name}：{companion}")
      old_profile = str(self.memory.get("profile_prompt", "") or "").strip() or "暂无。"
      p = (
        "你是光遇AI伴侣的长期记忆整理器。请把最近对话整合成一段可直接放进聊天提示词的长期理解。\n"
        "目标：让AI越来越了解使用者，而不是死记原句。\n"
        "要求：\n"
        "1. 只保留稳定信息：使用者称呼、关系氛围、偏好、讨厌点、常见玩法、说话风格、当前持续状态。\n"
        "2. 删除一次性寒暄、重复句、OCR乱码、系统提示、明显误识别、API/程序/日志相关内容。\n"
        "3. 不要编造，不确定就别写。\n"
        "4. 写给AI自己看，用第二人称/指令式都可以，中文，短句。\n"
        "5. 最近状态必须写成“最近/上次...”，不要当成永久事实。\n"
        "6. 控制在350字以内，只输出整理后的记忆正文。\n\n"
        "已有长期理解：\n" + old_profile + "\n\n"
        "最近对话素材：\n" + "\n\n".join(transcript)
      )
      self._log("Mem: updating")
      r = self._chat_completion(p, temperature=0.2, max_tokens=520)
      ans = r.choices[0].message.content.strip() if r.choices else ""
      summary = self._clean_memory_summary(ans)
      if len(summary) >= 20:
        self.memory = update_memory_profile(self.memory, summary)
        self._log("Mem: updated")
      else:
        self._log("Mem: skipped")
    except Exception as e:
      self._log("Mem: " + str(e)[:60])
    finally:
      self.memory_updating = False

  def _ch(self, txt):
    if not txt: return ""
    try:
      recent = " | ".join(self.my_words[-4:])
      p = (
        "你的名字是" + self.companion_name + "。你是光遇里的真人朋友，不是工具。\n"
        "玩家在光遇里的称呼/备注名是：" + self.user_call_name + "\n"
        "你的性格提示词：" + self.personality_prompt + "\n"
        "长期记忆：\n" + memory_prompt(self.memory) + "\n"
        "最近对话：\n" + self._recent_dialogue_prompt() + "\n"
        "下面给你的是当前屏幕上识别到的白色中文字列表，里面可能混着聊天、UI、活动标题、物品名、玩家备注、你自己刚说过的话。\n"
        "你要先从列表里判断有没有“玩家最新对你说的话”。如果没有，就输出 EMPTY。\n"
        "只有当玩家在跟你打招呼、问你、喊你、接你的话、给你指令、或上下文自然需要回应时才回复。\n"
        "玩家催你说话、问你在不在、说你不说话/哑巴了吗/理我/回话时，一定要自然回应。\n"
        "玩家问你是谁、问你为什么卡、问扫描/识别是不是错了，也要自然回应，不要输出 EMPTY。\n"
        "玩家表达情绪、吐槽、抱怨、调侃时也要自然接一句，比如“我服”“别狂了”“笑死”。\n"
        "忽略系统文字、物品/活动标题、残缺半句、备注名、自己刚说的话、以及不需要接话的文字。\n"
        "遇到乱码、错别字堆、半截输入、只带省略号的文字，看不懂就输出 EMPTY，不要说“你打错字了”。\n"
        "不要主动把话题转成跑图/任务；只有玩家明确问跑图、任务、去不去、走不走时，才接这个话题。\n"
        "如果前后文看起来已经回过了，也输出 EMPTY。\n"
        "不要每句都喊玩家称呼，只有自然时才喊。\n"
        "如果要回复，用中文，6-18个字，像真人朋友，短一点。\n"
        "只输出回复正文或 EMPTY，不要解释你的判断。\n"
        "你刚说过的话只用于识别回声，不要继续复读：" + recent + "\n"
        "屏幕白色文字列表：\n" + txt
      )
      r = self._chat_completion(p, temperature=0.9, max_tokens=60)
      ans = r.choices[0].message.content.strip() if r.choices else ""
      return "" if ans.upper() == "EMPTY" else ans
    except Exception as e:
      self._log("DS: " + str(e)[:60])
      return ""

  def run(self):
    self._log("Start")
    for i in range(15):
      if window_exists(): break
      time.sleep(1)
    if not window_exists(): self._log("No window"); return
    activate_sky_window(); time.sleep(0.3)
    self._log("Ready")
    self.last_time = time.time()

    while True:
      try:
        time.sleep(0.3)
        # 刚发完消息时，画面里的聊天气泡大概率是自己的回声，先短暂静默。
        if time.time() - self.last_sent_at < SELF_ECHO_SILENCE:
          continue
        stable_msg = self._take_stable_candidate()
        if stable_msg:
          if self._is_self_echo(stable_msg):
            self._log("Echo: " + stable_msg[:60])
            continue
          if self._ignored_recently(stable_msg):
            continue
          if not self._seen_recently(stable_msg):
            if time.time() - self.last_time < REPLY_COOLDOWN:
              self.pending_msg = stable_msg
              self.pending_since = time.time()
              self._log("Hold: " + stable_msg[:60])
            else:
              self._send_reply(stable_msg)
          continue
        if self.candidate_msg:
          continue
        if self.pending_msg and time.time() - self.last_time >= REPLY_COOLDOWN:
          msg = self.pending_msg
          self.pending_msg = ""
          if not self._seen_recently(msg):
            self._send_reply(msg)
          continue
        if time.time() < self.next_ocr_at:
          continue
        if not sky_window_foreground():
          if time.time() - self.last_not_foreground_log > 8:
            self._log("Watch: 光遇不在前台，暂停识别。")
            self.last_not_foreground_log = time.time()
          continue
        shot = capture_window()
        if not shot: continue
        if not self._changed(shot): continue

        # 画面变了，OCR获取当前文字
        now = self._do_ocr(shot)
        self.next_ocr_at = time.time() + OCR_MIN_INTERVAL
        if not now:
          self.empty_ocr_count += 1
          if time.time() - self.last_empty_ocr_log > 8:
            tip = "OCR: empty"
            if self.empty_ocr_count >= 3:
              tip += " (检查光遇窗口是否可见、聊天文字是否太小/被遮挡；Gemini只做兜底)"
            self._log(tip)
            self.last_empty_ocr_log = time.time()
          continue
        self.empty_ocr_count = 0

        new_msg = self._parse_vision_text(now)
        if not new_msg:
          continue
        fresh_msg = self._fresh_screen_text(new_msg)
        if not fresh_msg:
          continue
        new_msg = fresh_msg

        if self._ignored_recently(new_msg):
          continue

        if self._is_self_echo(new_msg):
          if not self._same(new_msg, self.last_ignored_text):
            self._log("Echo: " + new_msg[:60])
          self.last_ignored_text = new_msg
          self.echo_backoff_until = time.time() + ECHO_BACKOFF
          self.next_ocr_at = max(self.next_ocr_at, self.echo_backoff_until)
          continue

        if self._seen_recently(new_msg):
          continue

        if self._scanned_recently(new_msg):
          continue

        if self._is_too_fragmentary(new_msg):
          self._log("Skip: " + new_msg.replace("\n", " | ")[:80])
          self._mark_seen(new_msg, replied=False)
          continue

        self._mark_scanned(new_msg)
        self._hold_candidate(new_msg)
        self.next_ocr_at = max(self.next_ocr_at, time.time() + MSG_STABLE_SECONDS)
      except KeyboardInterrupt:
        self._log("Bye"); break
      except Exception as e:
        self._log("E: " + str(e)[:60])
