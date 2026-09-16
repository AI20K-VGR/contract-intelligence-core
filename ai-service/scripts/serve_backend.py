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
    uvicorn.run("contract_ocr.web.app:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
