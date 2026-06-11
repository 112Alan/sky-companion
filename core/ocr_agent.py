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
Extract the newest Chinese chat bubble message.
Read text inside chat bubbles first. If there are multiple chat bubbles, return the newest readable one.
Ignore player names, friend remarks/nicknames above avatars, UI text, menus, buttons, system tips, subtitles, and old menu text.
Do not return names alone.
If no chat bubble message is visible, return EMPTY.
Return only the chat message text itself, with no speaker name, no JSON, no labels, no quotes.
Return the complete chat bubble sentence. Do not return only the first few characters.
If the message looks cut off, incomplete, or only partly readable, return EMPTY and wait for a clearer frame."""

SELF_ECHO_SILENCE = 2.0
SELF_ECHO_WINDOW = 30.0
OCR_MIN_INTERVAL = 0.8
ECHO_BACKOFF = 2.0
MSG_STABLE_SECONDS = 1.4
DEFAULT_IGNORE_REMARKS = ["大号", "小号", "好友", "备注", "主人"]

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
    """兼容纯文本、完整JSON和Gemini偶尔吐出的半截JSON。"""
    txt = (txt or "").strip()
    if not txt or txt.upper() == "EMPTY":
      return ""
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.I | re.S).strip()

    # Gemini有时会输出半截JSON。只有拿到message字段时才使用，只有speaker则当作无消息。
    if "speaker" in txt.lower() or "message" in txt.lower() or txt.startswith("{"):
      msg_match = re.search(r'"message"\s*:\s*"([^"\r\n}]*)', txt, re.I)
      if msg_match:
        msg = msg_match.group(1).strip()
        return "" if self._is_remark_or_name(msg) else msg
      msg_match = re.search(r"'message'\s*:\s*'([^'\r\n}]*)", txt, re.I)
      if msg_match:
        msg = msg_match.group(1).strip()
        return "" if self._is_remark_or_name(msg) else msg
      try:
        data = json.loads(txt)
        if isinstance(data, dict):
          msg = (data.get("message") or data.get("text") or "").strip()
          return "" if self._is_remark_or_name(msg) else msg
      except Exception:
        pass
      return ""

    try:
      data = json.loads(txt)
      if isinstance(data, dict):
        msg = (data.get("message") or data.get("text") or "").strip()
        return "" if self._is_remark_or_name(msg) else msg
    except Exception:
      pass
    lines = [l.strip() for l in txt.split("\n") if re.search(r"[\u4e00-\u9fff]", l)]
    msg = "\n".join(lines).strip()
    return "" if self._is_remark_or_name(msg) else msg

  def _is_self_echo(self, txt):
    """判断OCR内容是不是自己刚发出去的话。"""
    if not txt:
      return False
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
    if self._is_remark_or_name(txt):
      return False
    if self._is_self_echo(txt):
      return False
    ui_words = ["确定", "取消", "设置", "返回", "跳过", "领取", "商店", "好友", "任务", "邀请", "服务器", "连接"]
    if clean in ui_words:
      return False
    return True

  def _changed(self, shot):
    arr = np.array(shot)
    if self.prev is not None and arr.shape == self.prev.shape:
      diff = np.mean(np.abs(arr - self.prev))
      self.prev = arr.copy()
      return diff > 15
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
        ]}],"max_tokens":80},
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
    clean = self._clean_text(txt)
    if not clean:
      return True
    now = time.time()
    self.replied_msgs = [(old, ts) for old, ts in self.replied_msgs if now - ts < 45]
    for old, ts in self.replied_msgs:
      old_clean = self._clean_text(old)
      if not old_clean:
        continue
      if old_clean == clean:
        return True
      # OCR often returns a half sentence after a reply, e.g. "你好" from "你好伴侣名".
      if len(clean) >= 2 and len(old_clean) >= 2 and (clean in old_clean or old_clean in clean):
        return True
    return False

  def _mark_seen(self, txt):
    if not txt:
      return
    self.seen.append(txt)
    self.replied_msgs.append((txt, time.time()))
    if len(self.seen) > 50:
      self.seen = self.seen[-50:]
    if len(self.replied_msgs) > 30:
      self.replied_msgs = self.replied_msgs[-30:]

  def _send_reply(self, new_msg):
    """对一条确认过的玩家新消息生成回复并打进游戏。"""
    self._log("New: " + new_msg[:60])

    reply = self._ch(new_msg)
    self._log("DS: " + (reply[:50] if reply else "empty"))
    if not reply:
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
    self._mark_seen(new_msg)
    self.memory = add_memory(new_msg, reply)
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
        "Reply in Chinese, 6-18 chars, natural and short.\n"
        "Only answer the Player message below. Do not continue your own previous topic.\n"
        "Do not invent facts like what you did last night.\n"
        "If Player text is incomplete, only a name, OCR junk, or not worth replying, output EMPTY.\n"
        "Your recent replies for echo detection, do not answer them: " + recent + "\n"
        "Player: " + txt
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
          if self._should_reply(stable_msg) and not self._seen_recently(stable_msg):
            if time.time() - self.last_time < 3:
              self.pending_msg = stable_msg
              self.pending_since = time.time()
              self._log("Hold: " + stable_msg[:60])
            else:
              self._send_reply(stable_msg)
          continue
        if self.pending_msg and time.time() - self.last_time >= 3:
          msg = self.pending_msg
          self.pending_msg = ""
          if not self._seen_recently(msg) and self._should_reply(msg):
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

        if self._is_self_echo(new_msg):
          if not self._same(new_msg, self.last_ignored_text):
            self._log("Echo: " + new_msg[:60])
          self.last_ignored_text = new_msg
          self.echo_backoff_until = time.time() + ECHO_BACKOFF
          self.next_ocr_at = max(self.next_ocr_at, self.echo_backoff_until)
          continue

        if not self._should_reply(new_msg):
          self._log("Skip: " + new_msg[:60])
          self._mark_seen(new_msg)
          continue

        if self._seen_recently(new_msg):
          continue

        # 排除自己刚说的话（字符重叠率>50%就算重复）
        for w in self.my_words[-4:]:
          if w and len(w) > 5:
            common = sum(1 for c in w if c in new_msg)
            if common / max(len(w), 1) > 0.5:
              # 从new_msg中移除重叠部分
              for c in w:
                if c in new_msg:
                  new_msg = new_msg.replace(c, "", 1)
              new_msg = new_msg.strip()
        if not new_msg: continue
        # 去掉标点符号
        clean = re.sub(r"[\s.。，,！!？?~～、]", "", new_msg).strip()
        if len(clean) < 2:
          continue

        self._hold_candidate(new_msg)
      except KeyboardInterrupt:
        self._log("Bye"); break
      except Exception as e:
        self._log("E: " + str(e)[:60])
