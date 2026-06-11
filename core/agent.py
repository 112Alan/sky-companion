# -*- coding: utf-8 -*-
"""Sky Companion - Auto Agent (reactive mode)"""
import time, os, sys
from datetime import datetime
from core.screen_capture import capture_window, window_exists
from core.game_controller import GameController, activate_sky_window
from core.user_settings import ensure_settings
from knowledge.dialogue import DialogueEngine
from config import DEFAULT_MODE

MOVE_INTERVAL = 15.0

class CompanionAgent:
    def __init__(self, settings=None, mode=DEFAULT_MODE):
        self.settings = settings or ensure_settings()
        if not self.settings:
            raise SystemExit(1)
        self.controller = GameController()
        self.dialogue = DialogueEngine(settings=self.settings, mode=mode)
        self.running = True
        self.last_move_time = 0

    def _log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        print(f"[{t}] {msg}")

    def _walk(self):
        import random
        d = random.choice(["move_forward", "move_left", "move_right"])
        dur = random.uniform(0.3, 0.8)
        fn = getattr(self.controller, d)
        fn(dur)
        time.sleep(0.3)

    def run(self):
        self._log("启动伴游模式...")
        self._log("AI 会在光遇里走动，等你来找它")
        self._log("想和 AI 说话，在手机上靠近它，然后切换到 PowerShell 打字")
        for i in range(30):
            if window_exists(): break
            if i % 10 == 0: self._log("等待光遇窗口...")
            time.sleep(1)
        self._log("激活窗口...")
        activate_sky_window()
        time.sleep(2)

        # 进游戏后打个招呼
        if self.dialogue and self.dialogue.client:
            try:
                g = self.dialogue.get_greeting()
                self._log("进游戏: " + g)
                self.controller.send_chat_message(g)
                time.sleep(2)
            except:
                pass

        self._log("AI 已在游戏中，你可以打字和它聊天了")
        self._log("输入消息按回车，AI 会在游戏里回复你")
        print()

        try:
            while self.running:
                now = time.time()
                if now - self.last_move_time >= MOVE_INTERVAL:
                    self.last_move_time = now
                    self._walk()

                try:
                    user = input("> ").strip()
                    if user in ("exit", "quit"):
                        self._log("结束")
                        self.running = False
                        break
                    if user:
                        if self.dialogue and self.dialogue.client:
                            resp, acts = self.dialogue.generate_response(user)
                            self._log(f"AI: {resp[:60]}")
                            self.controller.send_chat_message(resp[:80])
                        else:
                            self._log("AI 未连接（需要 API Key）")
                except (EOFError, KeyboardInterrupt):
                    self._log("结束")
                    self.running = False
                    break

        except KeyboardInterrupt:
            self._log("停止")
        except Exception as e:
            self._log("错误: " + str(e))
            import traceback
            traceback.print_exc()
