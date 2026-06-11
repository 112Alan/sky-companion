# -*- coding: utf-8 -*-
"""
Sky Companion - AI 决策引擎
"""

from core.game_controller import GameController
from core.user_settings import ensure_settings
from knowledge.dialogue import DialogueEngine
from config import DEFAULT_MODE

class DecisionEngine:
    def __init__(self, settings=None):
        self.settings = settings or ensure_settings()
        if not self.settings:
            raise SystemExit(1)
        self.controller = GameController()
        self.dialogue = DialogueEngine(settings=self.settings, mode=DEFAULT_MODE)
        self.last_action = None

    def process(self, user_input, screenshot_path=None):
        dialog, actions = self.dialogue.generate_response(user_input, screenshot_path)
        self._execute_actions(actions)
        self.last_action = {"input": user_input, "dialog": dialog, "actions": actions}
        return dialog, actions

    def process_proactive(self):
        dialog, actions = self.dialogue.generate_proactive()
        self._execute_actions(actions)
        return dialog, actions

    def _execute_actions(self, actions):
        for a in actions:
            self._execute_action(a)

    def _execute_action(self, a):
        if isinstance(a, str):
            a = a.strip().lower()
            if a == "fly": self.controller.fly(1.0)
            elif a == "walk_forward": self.controller.move_forward(0.5)
            elif a == "jump": self.controller.jump()
            elif a == "interact": self.controller.interact()
            elif a.startswith("emote:"):
                self.controller.use_emote_by_name(a.split(":",1)[1].strip())
            elif a == "sit": self.controller.use_emote_by_name("坐下")
            elif a == "hold_hand": self.controller.use_emote_by_name("牵手")
            elif a == "hug": self.controller.use_emote_by_name("拥抱")
            elif a == "look_around": self.controller.look_around()
            elif a == "wait": self.controller.wait(1.0)
