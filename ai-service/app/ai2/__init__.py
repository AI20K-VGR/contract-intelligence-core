"""Versioned public package API for the AI2 processing runtime."""

from __future__ import annotations

PACKAGE_NAME = "vsf-ai2"
PACKAGE_VERSION = "1.0.0"
__version__ = PACKAGE_VERSION

from app.ai2.v1 import process_files, process_payloads, process_payloads_full  # noqa: E402,F401

__all__ = ["PACKAGE_NAME", "PACKAGE_VERSION", "__version__", "process_files", "process_payloads", "process_payloads_full"]
