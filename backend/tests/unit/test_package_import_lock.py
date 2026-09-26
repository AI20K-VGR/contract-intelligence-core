"""Import-lock regression test (Phase 2, repo-hygiene-restructure).

Locks the current import surface of the backend package
(`backend/pyproject.toml:156` -> `pythonpath = ["src"]`, wheel
`packages = ["src/contract_intelligence"]`) so a later restructure cannot
silently break resolution. Does NOT call `git` and does NOT import the
ai-service package (`contract_ocr` / `app`).
"""

import contract_intelligence  # noqa: F401


def test_contract_intelligence_importable() -> None:
    assert contract_intelligence is not None
