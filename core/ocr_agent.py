# -*- coding: utf-8 -*-
"""Sky Companion - screenshot OCR chat agent."""
import sys, os, time, re, base64, io, json, requests, numpy as np
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.screen_capture import capture_window, window_exists
from core.game_controller import activate_sky_window, GameController
from core.user_settings import add_memory, chat_url, ensure_settings, load_memory, memory_prompt
from openai import OpenAI

ctrl = GameController()

VISION_PROMPT = """You are reading a Sky: Children of the Light screenshot.
Extract ALL clearly visible WHITE Chinese text in the screenshot.
Return one text item per line.
Keep short text exactly as visible.
Include white chat bubbles and white UI text; do not decide what is chat.
Ignore colored, gray, transparent, blurred, or unreadable text.
Do not output JSON, speaker labels, explanations, or quotes.
If no clear white Chinese text is visible, return EMPTY."""

SELF_ECHO_SILENCE = 2.0
SELF_ECHO_WINDOW = 30.0
OCR_MIN_INTERVAL = 0.6
ECHO_BACKOFF = 2.0
MSG_STABLE_SECONDS = 0.9
REPLY_COOLDOWN = 1.2
CHANGE_THRESHOLD = 10
DEFAULT_IGNORE_REMARKS = ["大号", "小号", "好友", "备注", "主人"]
UI_TEXT_HINTS = [
  "狂欢", "狂欢季", "季节", "先祖", "编钟", "任务", "活动", "礼包", "商店", "蜡烛",
  "爱心", "斗篷", "发型", "面具", "乐器", "兑换", "领取", "剩余", "点击",
]
CHAT_HINTS = [
  "你好", "哈喽", "嗨", "早上好", "晚上好", "晚安", "在吗", "走", "来", "去",
  "你", "我", "咱", "我们", "怎么", "为什么", "什么", "哪", "喊", "吗", "呢",
  "别", "服", "烦", "笑死", "草", "靠", "无语", "救命", "行", "好",
  "？", "?", "！", "!",
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
    self.replied_msgs = []
    self.ignored_msgs = []
    self.dialogue_turns = []

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

  def _contains_clean(self, a, b, min_len=2):
    ca = self._clean_text(a)
    cb = self._clean_text(b)
    if len(ca) < min_len or len(cb) < min_len:
      return False
    return ca in cb or cb in ca

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
      if self._same(txt, self.last_sent_text):
        return True
      clean_new = self._clean_text(txt)
      clean_self = self._clean_text(self.last_sent_text)
      if clean_new and clean_self and (clean_new in clean_self or clean_self in clean_new):
        return True
    for w in self.my_words[-4:]:
      if w and (self._same(txt, w) or self._contains_clean(txt, w)):
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
    if time.time() - self.candidate_since < MSG_STABLE_SECONDS:
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
    if len(clean) <= 6 and clean[-1] in "的在把被给和跟又该新":
      return True
    if clean in ("什么", "怎么", "你该", "怎么又"):
      return True
    return False

  def _looks_like_ui_text(self, txt):
    clean = self._clean_text(txt)
    if not clean:
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
    if any(h in txt for h in CHAT_HINTS):
      return True
    # 稍长的句子没有明显UI词时，先当作可能的人话。
    return len(clean) >= 7

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
      kept.append(line)
    return "\n".join(kept)

  def _conversation_key(self, txt):
    filtered = self._filter_screen_text(txt)
    lines = [self._clean_text(l) for l in filtered.split("\n") if self._clean_text(l)]
    if lines:
      best = max(lines, key=len)
    else:
      best = self._clean_text(txt)
    return re.sub(r"(吗|呢|啊|呀|吧|嘛|哈)+$", "", best)

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
      if old_clean == clean:
        return True
      if is_block or "\n" in (old or ""):
        continue
      if len(clean) >= 2 and len(old_clean) >= 2 and (clean in old_clean or old_clean in clean):
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

  def _do_ocr(self, shot=None):
    """Gemini识图（通过hohoapi）"""
    shot = shot or capture_window()
    if not shot: return ""
    shot = shot.resize((shot.width*3//4, shot.height*3//4))
    buf = io.BytesIO(); shot.save(buf, format="JPEG", quality=50)
    b64 = base64.b64encode(buf.getvalue()).decode()
    t0 = time.time()
    try:
      r = requests.post(chat_url(self.vision["base_url"]),
        headers={"Authorization":"Bearer " + self.vision["api_key"],"Content-Type":"application/json"},
        json={"model":self.vision["model"],"messages":[{"role":"user","content":[
          {"type":"text","text":self._vision_prompt()},
          {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64}}
        ]}],"max_tokens":220},
        timeout=15)
      t = r.json()["choices"][0]["message"]["content"].strip() if r.status_code==200 else ""
      if t:
        t = self._parse_vision_text(t)
        if t: return t
    except Exception as e:
      self._log("V: " + str(e)[:60])
    return ""

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
      if old_clean == clean:
        return True
      if is_block or "\n" in (old or ""):
        continue
      # OCR often returns a half sentence after a reply, e.g. "你好" from "你好伴侣名".
      if len(clean) >= 2 and len(old_clean) >= 2 and (clean in old_clean or old_clean in clean):
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
    if len(self.seen) > 50:
      self.seen = self.seen[-50:]
    if len(self.replied_msgs) > 30:
      self.replied_msgs = self.replied_msgs[-30:]
    if len(self.ignored_msgs) > 30:
      self.ignored_msgs = self.ignored_msgs[-30:]

  def _send_reply(self, new_msg):
    """对一条确认过的玩家新消息生成回复并打进游戏。"""
    filtered_msg = self._filter_screen_text(new_msg)
    if not filtered_msg:
      self._log("Skip: " + new_msg.replace("\n", " | ")[:80])
      self._mark_seen(new_msg, replied=False)
      return False
    self._log("New: " + filtered_msg.replace("\n", " | ")[:80])

    reply = self._ch(filtered_msg)
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
    return True

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
        "玩家表达情绪、吐槽、抱怨、调侃时也要自然接一句，比如“我服”“别狂了”“笑死”。\n"
        "忽略系统文字、物品/活动标题、残缺半句、备注名、自己刚说的话、以及不需要接话的文字。\n"
        "如果前后文看起来已经回过了，也输出 EMPTY。\n"
        "不要每句都喊玩家称呼，只有自然时才喊。\n"
        "如果要回复，用中文，6-18个字，像真人朋友，短一点。\n"
        "只输出回复正文或 EMPTY，不要解释你的判断。\n"
        "你刚说过的话只用于识别回声，不要继续复读：" + recent + "\n"
        "屏幕白色文字列表：\n" + txt
      )
      r = self.dclient.chat.completions.create(model=self.chat["model"],messages=[{"role":"user","content":p}],temperature=0.9,max_tokens=60)
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
        shot = capture_window()
        if not shot: continue
        if not self._changed(shot): continue

        # 画面变了，OCR获取当前文字
        now = self._do_ocr(shot)
        self.next_ocr_at = time.time() + OCR_MIN_INTERVAL
        if not now:
          if time.time() - self.last_empty_ocr_log > 8:
            self._log("OCR: empty")
            self.last_empty_ocr_log = time.time()
          continue

        new_msg = self._parse_vision_text(now)
        if not new_msg:
          continue

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

        self._hold_candidate(new_msg)
        self.next_ocr_at = max(self.next_ocr_at, time.time() + MSG_STABLE_SECONDS)
      except KeyboardInterrupt:
        self._log("Bye"); break
      except Exception as e:
        self._log("E: " + str(e)[:60])
