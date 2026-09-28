#!/usr/bin/env python3
"""_errors.py — the install package's one error type (extracted from
install.py so submodules can raise it without importing the orchestrator)."""


class InstallError(Exception):
    """A deployer-actionable failure (bad input) — the message names the file
    and the fix so the installer reports it plainly instead of dumping a raw
    traceback at onboarding time."""
