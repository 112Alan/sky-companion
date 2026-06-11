# -*- coding: utf-8 -*-
"""Sky Companion - Web Chat Server
Mobile-friendly web chat that types AI responses into Sky game
"""
import sys, os, json, threading, time, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from core.game_controller import GameController, activate_sky_window
from core.screen_capture import capture_window, window_exists
from core.user_settings import ensure_settings
from knowledge.dialogue import DialogueEngine
from config import DEFAULT_MODE

# Global state
controller = GameController()
dialogue = None
last_responses = []
HOST = "0.0.0.0"
PORT = 9876

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sky Companion</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; height: 100vh; display: flex; flex-direction: column; }
.header { background: #16213e; padding: 16px; text-align: center; font-size: 18px; font-weight: 600; color: #e94560; }
.chat { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.msg { max-width: 80%; padding: 10px 14px; border-radius: 16px; font-size: 15px; line-height: 1.4; word-break: break-word; }
.you { align-self: flex-end; background: #0f3460; }
.ai { align-self: flex-start; background: #16213e; border: 1px solid #333; }
.mode-tag { font-size: 11px; color: #e94560; text-align: center; padding: 8px; }
.input-area { display: flex; padding: 12px; gap: 8px; background: #16213e; }
.input-area input { flex: 1; padding: 12px; border: none; border-radius: 24px; background: #0f3460; color: #eee; font-size: 15px; outline: none; }
.input-area button { padding: 12px 20px; border: none; border-radius: 24px; background: #e94560; color: #fff; font-size: 15px; cursor: pointer; }
.switch-row { display: flex; gap: 4px; padding: 8px 12px; justify-content: center; }
.switch-btn { padding: 4px 12px; border: 1px solid #333; border-radius: 12px; background: transparent; color: #aaa; font-size: 12px; cursor: pointer; }
.switch-btn.active { background: #e94560; border-color: #e94560; color: #fff; }
</style></head><body>
<div class="header">Sky Companion</div>
<div class="switch-row" id="modes"></div>
<div class="chat" id="chat"></div>
<div class="input-area">
  <input id="input" placeholder="Message..." onkeydown="if(event.key=='Enter')send()">
  <button onclick="send()">Send</button>
</div>
<script>
const modes = ["\u6b63\u5e38","\u865a\u604b","\u75c5\u604b","\u8650\u604b"];
let currentMode = "\u6b63\u5e38";
modes.forEach(m => {
  const btn = document.createElement("button");
  btn.className = "switch-btn" + (m===currentMode?" active":"");
  btn.textContent = m;
  btn.onclick = () => {
    fetch("/mode?m="+encodeURIComponent(m)).then(r=>r.text()).then(()=>{
      document.querySelectorAll(".switch-btn").forEach(b=>b.classList.remove("active"));
      btn.classList.add("active");
      currentMode = m;
      addMsg("Mode: " + m, "ai");
    });
  };
  document.getElementById("modes").appendChild(btn);
});

function addMsg(text, cls) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  document.getElementById("chat").appendChild(d);
  d.scrollIntoView({behavior:"smooth"});
}

function send() {
  const input = document.getElementById("input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  addMsg(msg, "you");
  fetch("/chat?msg="+encodeURIComponent(msg)).then(r=>r.json()).then(d=>{
    if (d.reply) addMsg(d.reply, "ai");
  }).catch(()=>addMsg("Error", "ai"));
}

// Auto-refresh for Sky game screen status
setInterval(() => {
  fetch("/status").then(r=>r.json()).then(d=>{
    if (d.last_reply) {
      const last = document.getElementById("chat").lastChild;
      if (last && last.textContent === d.last_reply) return;
      addMsg(d.last_reply, "ai");
    }
  }).catch(()=>{});
}, 3000);
</script></body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        
        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
        
        elif path == "/chat":
            msg = qs.get("msg", [""])[0]
            if msg and dialogue:
                try:
                    # Also send to game chat
                    controller.send_chat_message(msg[:80])
                    time.sleep(0.5)
                    # Get AI reply
                    reply, actions = dialogue.generate_response(msg)
                    if reply:
                        # Type AI reply in game
                        controller.send_chat_message(reply[:80])
                        last_responses.append(reply)
                        if len(last_responses) > 10: last_responses.pop(0)
                        self._json({"reply": reply})
                    else:
                        self._json({"reply": "..."})
                except Exception as e:
                    self._json({"reply": f"Error: {e}"})
            else:
                self._json({"reply": "AI not connected"})
        
        elif path == "/mode":
            m = qs.get("m", ["\u6b63\u5e38"])[0]
            if dialogue:
                dialogue.set_mode(m)
            self._json({"ok": True})
        
        elif path == "/status":
            self._json({"last_reply": last_responses[-1] if last_responses else ""})
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    
    def log_message(self, *a): pass


def main():
    global dialogue
    settings = ensure_settings()
    if not settings:
        return
    dialogue = DialogueEngine(settings=settings, mode=DEFAULT_MODE)
    
    # Activate Sky window
    print("Looking for Sky window...")
    for i in range(20):
        if window_exists(): break
        time.sleep(1)
    
    if window_exists():
        print("Sky window found!")
        activate_sky_window()
        time.sleep(1)
    else:
        print("Sky window not found - chat typing disabled")
    
    if dialogue and dialogue.client:
        g = dialogue.get_greeting()
        print(f"Mode: {dialogue.mode} - {g}")
        controller.send_chat_message(g)
    
    # Start server
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Open this URL on your phone: http://{HOST}:{PORT}")
    print(f"Or on this PC: http://localhost:{PORT}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped")

if __name__ == "__main__":
    main()
