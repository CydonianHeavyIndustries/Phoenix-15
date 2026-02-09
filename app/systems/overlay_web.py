import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Optional
from urllib.parse import urlparse

from config import VR_OVERLAY_ENABLED, VR_OVERLAY_PORT

_server: Optional[HTTPServer] = None
_thread: Optional[threading.Thread] = None
_ptt_cb: Optional[Callable[[str], None]] = None


INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Bjorgsun-26 — VR PTT</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <style>
    html, body { margin:0; height:100%; background:#000b10; overflow:hidden; }
    .wrap { position:fixed; inset:0; display:flex; align-items:center; justify-content:center; }
    .btn {
      width: 280px; height: 280px; border-radius: 50%;
      background: radial-gradient(circle at 30% 30%, #0aa8d4 0%, #0a3752 70%, #05151c 100%);
      box-shadow: 0 0 32px rgba(36,199,255,0.35), inset 0 0 24px rgba(10,168,212,0.35);
      border: 4px solid #24c7ff; cursor: pointer; position: relative;
    }
    .btn:active { transform: scale(0.98); box-shadow: 0 0 18px rgba(36,199,255,0.5), inset 0 0 28px rgba(10,168,212,0.45); }
    .label { position:absolute; width:100%; text-align:center; bottom:-48px; color:#cfe8ff; font-family:Consolas, monospace; }
  </style>
  <script>
    function ping(path){ fetch(path).catch(()=>{}); }
    let toggled = false;
    function down(){ ping('/api/ptt/down'); }
    function up(){ ping('/api/ptt/up'); }
    function toggle(){ toggled = !toggled; ping('/api/ptt/toggle'); }
    window.addEventListener('keydown', e=>{ if(e.code==='Space'){ down(); } });
    window.addEventListener('keyup', e=>{ if(e.code==='Space'){ up(); } });
  </script>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"btn\" onmousedown=\"down()\" onmouseup=\"up()\" onclick=\"toggle()\"></div>
      <div class=\"label\">Push-to-Talk • Hold or Click to Toggle</div>
    </div>
  </body>
  </html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _ptt_cb
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            data = INDEX_HTML.encode("utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path.startswith("/api/ptt/"):
            action = parsed.path.rsplit("/", 1)[-1]
            if _ptt_cb is not None and action in {"down", "up", "toggle"}:
                try:
                    _ptt_cb(action)
                except Exception:
                    pass
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()


def set_ptt_callback(cb: Callable[[str], None]):
    global _ptt_cb
    _ptt_cb = cb


def start(port: int = VR_OVERLAY_PORT) -> bool:
    global _server, _thread
    if _server is not None:
        return True
    try:
        _server = HTTPServer(("127.0.0.1", int(port)), _Handler)
        _thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _thread.start()
        return True
    except Exception:
        _server = None
        return False


def stop():
    global _server
    try:
        if _server:
            _server.shutdown()
    except Exception:
        pass
    _server = None
