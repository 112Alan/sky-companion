# -*- coding: utf-8 -*-
"""Sky Companion - AI 聊天界面（回复打到游戏里）"""
import os
import sys
from colorama import init, Fore, Style
from core.screen_capture import capture_window, save_screenshot, window_exists
from core.game_controller import GameController, activate_sky_window
from core.user_settings import ensure_settings
from core.decision import DecisionEngine

init(autoreset=True)

class ChatInterface:
    def __init__(self, settings=None):
        self.settings = settings or ensure_settings()
        if not self.settings:
            raise SystemExit(1)
        self.engine = None
        self.controller = GameController()
        self.running = True

    def _activate_sky(self):
        if window_exists():
            print(Fore.GREEN + "[OK] 检测到光遇窗口" + Style.RESET_ALL)
            activate_sky_window()
            return True
        else:
            print(Fore.YELLOW + "[!] 未检测到光遇窗口，请先启动游戏" + Style.RESET_ALL)
            return False

    def display_banner(self):
        print(Fore.CYAN + "========================================")
        print("  Sky Companion - 光遇 AI 伴侣")
        print("  打字和 AI 聊天，AI 会在游戏里回复你")
        print("========================================" + Style.RESET_ALL)
        print(Fore.GREEN + "[OK] AI 已连接" + Style.RESET_ALL)
        print()
        print("使用说明：")
        print("  直接打字和 AI 聊天，AI 会在游戏里打字回复")
        print("  切换模式：正常 / 虚恋 / 病恋 / 虐恋")
        print("  输入 / 查看模式 | exit 退出")
        print()

    def run(self):
        self.engine = DecisionEngine(settings=self.settings)
        self.display_banner()
        self._activate_sky()

        if self.engine and self.engine.dialogue:
            g = self.engine.dialogue.get_greeting()
            print(Fore.CYAN + "[AI] " + g + Style.RESET_ALL)
        print()

        while self.running:
            try:
                ui = input(Fore.YELLOW + "你 > " + Style.RESET_ALL).strip()
                if not ui: continue
                if ui in ("exit", "quit", "退出"):
                    print(Fore.CYAN + "再见~" + Style.RESET_ALL)
                    self.running = False
                    break

                switched = False
                for mode in ["正常", "虚恋", "病恋", "虐恋"]:
                    if mode in ui and len(ui) < 10:
                        if self.engine and self.engine.dialogue:
                            self.engine.dialogue.set_mode(mode)
                            g = self.engine.dialogue.get_greeting()
                            print(Fore.CYAN + f"[{mode}] {g}" + Style.RESET_ALL)
                            self.controller.send_chat_message(g)
                            switched = True
                        break
                if switched:
                    print()
                    continue

                # Normal chat
                ss = None
                if window_exists():
                    try:
                        shot = capture_window()
                        if shot: ss = save_screenshot(shot)
                    except: pass

                dialog, actions = self.engine.process(ui, ss)
                print(Fore.CYAN + "[AI] " + dialog + Style.RESET_ALL)
                if actions:
                    print(Fore.GREEN + "[操作] " + " | ".join(actions) + Style.RESET_ALL)
                if dialog:
                    self.controller.send_chat_message(dialog[:80])
                print()

            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(Fore.RED + "错误: " + str(e) + Style.RESET_ALL)
