"""Dev server for the frontend (SE8 frontend, Team 08).

Serves this folder on http://localhost:8000 and forwards /api/* and /uploads/* requests to the Flask
backend (default http://localhost:5000), so the pages can keep calling "/api/..." with no CORS.

Run from the MINI-PROJECT/frontend folder:
    python serve.py
Optional: BACKEND=http://localhost:5001 python serve.py
"""
import functools
import http.server
import json
import os
import urllib.error
import urllib.request

BACKEND = os.environ.get("BACKEND", "http://localhost:5000")
PORT = int(os.environ.get("PORT", "8000"))
HERE = os.path.dirname(os.path.abspath(__file__))
PROXIED_PREFIXES = ("/api/", "/uploads/")  # uploaded product photos are served by Flask at /uploads/
FORWARD_HEADERS = ("Content-Type", "Authorization", "Idempotency-Key")


class Handler(http.server.SimpleHTTPRequestHandler):
    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(BACKEND + self.path, data=body, method=self.command)
        for name in FORWARD_HEADERS:
            if self.headers.get(name):
                req.add_header(name, self.headers[name])
        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as err:  # 4xx/5xx still carry a body we want to pass on
            resp = err
        except Exception:
            data = json.dumps({"error": "BACKEND_DOWN", "message": "Cannot reach the backend at " + BACKEND}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        data = resp.read()
        self.send_response(getattr(resp, "status", None) or resp.code)
        self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _api_or(self, fallback):
        if self.path.startswith(PROXIED_PREFIXES):
            self._proxy()
        else:
            fallback()

    def do_GET(self):
        self._api_or(super().do_GET)

    def do_POST(self):
        self._api_or(lambda: self.send_error(405))

    do_PUT = do_POST
    do_DELETE = do_POST


if __name__ == "__main__":
    handler = functools.partial(Handler, directory=HERE)
    print(f"Frontend: http://localhost:{PORT}  ->  /api/* proxied to {BACKEND}")
    http.server.ThreadingHTTPServer(("", PORT), handler).serve_forever()
