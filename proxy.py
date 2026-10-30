"""
MightPulse local proxy  –  http://localhost:8081
Serves index.html on /  and proxies /api/* -> https://api.mightpulse.com/v1/*
"""
import http.server
import socketserver
import urllib.request
import urllib.error
import json
import os
import sys

PORT = 8081
API_BASE = "https://api.mightpulse.com/v1"
ROOT = os.path.dirname(os.path.abspath(__file__))

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".png":  "image/png",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
}


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[proxy] {self.address_string()} {fmt % args}", flush=True)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "X-Api-Key, Authorization, Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        query = self.path[len(path):]   # includes leading "?" if present

        # ── /api/* → upstream API ────────────────────────────────────────
        if path.startswith("/api/"):
            upstream = API_BASE + path[4:] + query   # /api/players/123 → /v1/players/123
            api_key = (self.headers.get("X-Api-Key") or
                       self.headers.get("x-api-key") or "")
            req = urllib.request.Request(upstream)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", BROWSER_UA)
            if api_key:
                req.add_header("X-Api-Key", api_key)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self._cors()
                    self.end_headers()
                    self.wfile.write(body)
            except urllib.error.HTTPError as exc:
                body = exc.read()
                self.send_response(exc.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._cors()
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                body = json.dumps({"ok": False, "error": str(exc)}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._cors()
                self.end_headers()
                self.wfile.write(body)
            return

        # ── Static files ─────────────────────────────────────────────────
        rel  = path.lstrip("/") or "index.html"
        fpath = os.path.normpath(os.path.join(ROOT, rel))
        # Safety: don't escape root
        if not fpath.startswith(ROOT):
            self.send_response(403); self.end_headers(); return
        if not os.path.isfile(fpath):
            self.send_response(404); self.end_headers()
            self.wfile.write(b"Not found"); return
        ext = os.path.splitext(fpath)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"MightPulse proxy running at http://localhost:{PORT}", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        sys.stdout.flush()
        httpd.serve_forever()
