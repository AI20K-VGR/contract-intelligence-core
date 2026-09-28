#!/usr/bin/env python3
"""glossary_capture — deterministic "a term was coined but not glossed" detector.

The B-leg of the glossary capture funnel. Given a freshly-registered decision, it
flags when that DEC coins a load-bearing term (a backtick-wrapped identifier in
its title/rationale) that is NOT yet in the glossary SSOT. It rides the strong,
explicit DEC signal — a registered decision is where a team coins vocabulary — and
NEVER sniffs free prose, so the nudge stays sharp instead of crying wolf.

SCRIPT-only, pure judgment: it makes NO LLM call and never decides WHAT to record
(that is /hs:remember). It only answers "you just registered a DEC that coins
`X`, and the glossary does not have it — did you mean to add it?".

Signal (or None):
    {"type": "uncaptured_term", "terms": [<term>...], "dec": "DEC-N", "total": int}

Deterministic: same DEC + glossary → same signal. The git read (was the ledger
touched this session?) is isolated; the judgment is the pure `assess`, unit-tested
without a repo. ALWAYS degrades to None outside a git work tree — advisory is not
an error.

CLI:
    glossary_capture.py --root <project-dir>     # emit {signal: {...}|null}, exit 0
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(str(Path(__file__).resolve().parent))

SIGNAL_TYPE = "uncaptured_term"

# Cap on individually-named terms before the tail collapses to a count.
_TERM_CAP = 8

# A backtick-wrapped candidate is "term-like" only when it reads as a coined name:
# letters first, then letters/digits/space/underscore/hyphen/parens (covers
# `presence gate`, `kebab-term`, `snake_term`, `term (qualifier)`). Anything with
# a slash or a file extension is a path, not a term — excluded below.
_TERMISH = re.compile(r"^[A-Za-z][A-Za-z0-9 _()-]*$")
_PATHISH = re.compile(r"/|\.(py|md|ya?ml|json|sh|txt|toml|cfg|ini)$", re.I)
_BACKTICK = re.compile(r"`([^`]+)`")


def extract_terms(text: str) -> List[str]:
    """Backtick-wrapped, term-shaped tokens in `text`, sorted + de-duped. Drops
    paths (anything with a `/` or a file extension) and DEC ids — those are
    references, never coined terms."""
    out = []
    for raw in _BACKTICK.findall(text or ""):
        t = raw.strip()
        if not t or len(t) > 60:
            continue
        if _PATHISH.search(t) or t.upper().startswith("DEC-"):
            continue
        if not _TERMISH.match(t):
            continue
        out.append(t)
    return sorted(set(out))


def _is_known(term: str, glossary_terms: List[str]) -> bool:
    """True when `term` is already covered by the glossary. Substring match
    (case-insensitive) so a candidate `widget` is covered by a stored term cell
    `` `widget` `` or `` `widget` (UI) `` — loose by design to AVOID re-nudging a
    term the glossary effectively already holds."""
    low = term.lower()
    return any(low in (g or "").lower() for g in glossary_terms)


def assess(dec_changed: bool, latest_dec: Optional[Dict[str, Any]],
           glossary_terms: List[str]) -> Optional[Dict[str, Any]]:
    """Judge whether a freshly-registered DEC coined a term the glossary lacks.
    Pure + deterministic. Returns the signal dict or None.

    `dec_changed`: did the decision ledger move this session (git-derived).
    `latest_dec`: the most-recent decision record (id/title/rationale).
    `glossary_terms`: the term strings already in the glossary SSOT."""
    if not dec_changed or not latest_dec:
        return None
    text = "%s %s" % (latest_dec.get("title", ""), latest_dec.get("rationale", ""))
    candidates = extract_terms(text)
    fresh = sorted({c for c in candidates if not _is_known(c, glossary_terms)})
    if not fresh:
        return None
    return {"type": SIGNAL_TYPE, "terms": fresh[:_TERM_CAP],
            "dec": str(latest_dec.get("id", "")), "total": len(fresh)}


# ----------------------------------------------------------------------------
# IO (git + ledger + glossary); degrades to None, never raises
# ----------------------------------------------------------------------------

# The ledger surfaces the detector watches for a this-session change (YAML SSOT
# or the legacy markdown source).
_LEDGER_PATHS = ("docs/decisions.yaml", "docs/decisions.md")


def _ledger_changed(root: Path) -> bool:
    """True when the decision ledger is in the working-tree change set (a DEC was
    just registered, before it is committed) — the this-session anchor."""
    import decision_capture  # reuse the porcelain reader (DRY)
    for _status, path in decision_capture._porcelain_changes(root):
        if (path or "").replace("\\", "/") in _LEDGER_PATHS:
            return True
    return False


def _dec_num(rec: Dict[str, Any]) -> int:
    m = re.match(r"^DEC-(\d+)$", str(rec.get("id", "")))
    return int(m.group(1)) if m else -1


def _latest_dec(root: Path) -> Optional[Dict[str, Any]]:
    """The highest-id decision record, or None when the ledger is empty/absent."""
    import decision_register
    records = decision_register.parse_decisions(root)
    return max(records, key=_dec_num) if records else None


def _glossary_terms(root: Path) -> List[str]:
    import glossary_register
    return [t["term"] for t in glossary_register.list_terms(root)]


def collect(root) -> Optional[Dict[str, Any]]:
    """Assess the project at `root`: did a this-session DEC coin a glossary-less
    term? Returns the signal dict or None. Degrades to None on any IO error
    (advisory contract)."""
    rootp = Path(root)
    try:
        if not _ledger_changed(rootp):
            return None
        return assess(True, _latest_dec(rootp), _glossary_terms(rootp))
    except Exception:  # noqa: BLE001 — advisory: never crash the caller
        return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    try:
        signal = collect(Path(args.root).resolve())
    except Exception:  # noqa: BLE001
        signal = None
    print(json.dumps({"signal": signal}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
