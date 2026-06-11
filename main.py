# -*- coding: utf-8 -*-
"""Sky Companion"""
import sys, os
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except: pass
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.user_settings import ensure_settings

try:
    from colorama import init, Fore
    init(autoreset=True)
except ModuleNotFoundError:
    class Fore:
        CYAN = ""
        RESET = ""

def main():
    settings = ensure_settings()
    if not settings:
        return
    companion_name = settings["companion_name"]
    print(Fore.CYAN + "===================================")
    print(f"  {companion_name} - 光遇 AI 伴侣")
    print("===================================" + Fore.RESET)
    print(f"1) {companion_name}自动聊天")
    print("2) 网页聊天")
    print("3) 退出")
    print()
    try: c = input("选择 (1/2/3): ").strip()
    except: c = "1"
    if c == "3": return
    if c == "2":
        import web_server; web_server.main()
    else:
        from core.ocr_agent import SkyCompanionAgent
        SkyCompanionAgent(settings).run()

if __name__ == "__main__": main()
