"""Run the OCR backend API only (no UI). Interactive docs at http://127.0.0.1:8000/docs."""

import threading
import webbrowser
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

HOST = "127.0.0.1"
PORT = 8000


def _open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}/docs")


def main() -> None:
    # Loads OPENAI_API_KEY etc. from .env at the repo root, if present; see .env.example.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    threading.Timer(1.0, _open_browser).start()
    # http="h11": uvicorn's default "auto" prefers the httptools wheel, which on
    # some Windows setups installs without actually exposing HttpRequestParser
    # (AttributeError on the first request, server never crashes so it looks
    # fine until you try to use it). h11 is pure Python, already a transitive
    # dependency here, and plenty fast for a single-user local dev backend.
    uvicorn.run("contract_ocr.web.app:app", host=HOST, port=PORT, reload=False, http="h11")


if __name__ == "__main__":
    main()
