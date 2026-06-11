# -*- coding: utf-8 -*-
"""Config-driven dialogue engine with local long-term memory."""
import json
import re
from datetime import datetime

from openai import OpenAI

from config import COMPANION_MODES
from core.user_settings import add_memory, ensure_settings, load_memory, memory_prompt


def _system_prompt(settings, mode):
    name = settings["companion_name"]
    user_name = settings.get("user_call_name", "")
    personality = settings.get("personality_prompt", "")
    style = COMPANION_MODES.get(mode, COMPANION_MODES["正常"])["style"]
    memory = memory_prompt(load_memory())
    return f"""你的名字是「{name}」。你正在和玩家一起玩《光·遇》(Sky: Children of the Light)。

玩家在光遇里的称呼/备注名：{user_name}
你的性格提示词：{personality}
当前模式：{mode}，{style}

长期记忆：
{memory}

要求：
- 永远记得自己叫「{name}」，不要给自己改名。
- 像真实朋友一样说中文，短一点，自然一点。
- 不要把玩家的备注名、头顶名字、系统文字当成玩家对话。
- 只回答玩家刚刚说的话，不要续写你自己的上一句话。
- 回复必须是 JSON：{{"dialog":"你要说的话","actions":[],"search":""}}
"""


class DialogueEngine:
    def __init__(self, settings=None, mode="正常"):
        self.settings = settings or ensure_settings()
        if not self.settings:
            raise SystemExit(1)
        self.client = OpenAI(
            api_key=self.settings["chat"]["api_key"],
            base_url=self.settings["chat"]["base_url"],
        )
        self.model = self.settings["chat"]["model"]
        self.mode = mode
        self.messages = [{"role": "system", "content": _system_prompt(self.settings, self.mode)}]
        self.last_interaction = datetime.now()

    def set_mode(self, mode):
        if mode in COMPANION_MODES:
            self.mode = mode
            self.messages = [{"role": "system", "content": _system_prompt(self.settings, self.mode)}]
            return True
        return False

    def get_greeting(self):
        name = self.settings["companion_name"]
        return f"{name}上线啦。"

    def generate_response(self, user_input, screenshot_path=None):
        self.last_interaction = datetime.now()
        ctx = user_input
        if screenshot_path:
            ctx = "[截图: " + screenshot_path + "]\n" + ctx

        msgs = self.messages[-20:] + [{"role": "user", "content": ctx}]
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                temperature=0.8,
                max_tokens=300,
            )
            content = resp.choices[0].message.content.strip() if resp.choices else ""
            dialog, acts = self._parse_response(content)
            if dialog:
                add_memory(user_input, dialog)
            self.messages.append({"role": "user", "content": ctx})
            self.messages.append({"role": "assistant", "content": content})
            return dialog, acts
        except Exception:
            return "我这边有点卡，等我一下。", []

    def generate_proactive(self):
        return self.generate_response("玩家暂时没说话，你自然地说一句短话。")

    def _parse_response(self, content):
        text = content.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data.get("dialog", ""), data.get("actions", [])
        except Exception:
            pass
        return text, []
