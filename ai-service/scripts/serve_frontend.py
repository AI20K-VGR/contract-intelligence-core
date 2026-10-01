"""Serve the static frontend (frontend/index.html) — no Python deps, talks to the
backend over HTTP. Run scripts/serve_backend.py separately for the API."""

import functools
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 5500
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


def main() -> None:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(FRONTEND_DIR))
    threading.Timer(1.0, _open_browser).start()
    with ThreadingHTTPServer((HOST, PORT), handler) as httpd:
        print(f"Serving {FRONTEND_DIR} at http://{HOST}:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
