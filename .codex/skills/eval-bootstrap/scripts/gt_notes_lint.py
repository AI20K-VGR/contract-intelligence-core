#!/usr/bin/env python3
"""gt_notes_lint.py — deterministic notes-lint for the lỗ #1 fix.

The riskiest way to author ground truth is to copy the running system's output
and call it the answer key: a production bug then freezes into "truth" and the
eval can never catch it. The prevention layer is prose (data-workflow.md:
derive from spec first). THIS is the detection layer: scan each ground_truth.json
item's `notes`/`note` for bilingual (VI+EN) source-indicator phrases — the
author confessing in prose that the key came from the code/production — and FLAG
them.

Advisory by construction: exit 0 always in the default mode; `--strict` exits 1
when anything is flagged. The phrase list is deliberately broad (advisory noise
is cheap); it targets phrases that name production/the code as the SOURCE, never
every mention of "production" — good wording like "spec-derived, cross-checked
vs production" must stay clean.

Matching is diacritic-insensitive (NFD-fold) and case-insensitive so a phrase
written with or without Vietnamese tone marks still matches.

Stdlib only; never imports harness/scripts/ — self-contained like the rest of
this skill.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

from pathlib import Path

# Pinned source-indicator phrases (DP-5). The Vietnamese literals below are DATA
# (the strings the lint hunts for), not prose — the surrounding code stays
# English. Broad on purpose: advisory-only, so a wide net costs only mild noise.
SUSPECT_PHRASES = (
    # --- English ---
    "verified against production", "verified vs production", "from production output",
    "production output", "confirmed by running", "confirmed against the pipeline",
    "matches production", "matched production", "matches the code", "derived from output",
    "copied from output", "taken from output", "from the code", "by running the code",
    "ran the pipeline", "ran the code", "by executing the code", "by executing the pipeline",
    "reverse-engineered from output",
    "back-filled from output", "observed output as truth", "actual output as truth",
    "verified against prod", "matches prod", "from prod output",
    # --- Vietnamese ---
    "đối chiếu production", "đối chiếu với production", "xác nhận bằng production",
    "khớp với production", "lấy từ output", "lấy từ kết quả chạy", "chép từ output",
    "chạy code ra", "chạy pipeline ra", "suy từ output", "theo kết quả production",
    "theo output thực tế", "xác minh bằng cách chạy", "kết quả thực tế làm chuẩn",
    "lấy từ đầu ra", "khớp với code",
)


def _fold(text: str) -> str:
    """Lowercase + strip Vietnamese diacritics so a phrase matches whether or
    not the author typed the tone marks (NFD-decompose, drop combining marks,
    map đ->d)."""
    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in lowered if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d")


def _phrase_regex(folded_phrase: str):
    # word/hyphen boundaries so "the code" does not fire on "codebase" or
    # "non-production"; \s+ between words so a confession split across newlines
    # or padded with extra spaces still matches.
    # re.escape turns a space into "\ " (backslash-space); swap that for \s+ so
    # extra spaces / a newline between words still match.
    pattern = re.escape(folded_phrase).replace("\\ ", r"\s+")
    return re.compile(r"(?<![\w-])" + pattern + r"(?![\w-])")


_FOLDED_PHRASES = tuple((p, _fold(p), _phrase_regex(_fold(p))) for p in SUSPECT_PHRASES)


def scan_notes(text: str):
    """Return the original suspect phrases whose folded form appears in the
    folded notes text. A shorter phrase that is only matched because it is a
    substring of a longer matched phrase (e.g. the abbreviation "verified
    against prod" inside "verified against production") is dropped, so one
    confession is reported once, not twice."""
    if not text or not text.strip():
        return []
    folded = _fold(text)
    # word-boundary match, not bare substring: "the code" must not fire on
    # "codebase", "by executing" must not fire on "by executing the spec".
    hits = [(original, fp) for original, fp, rx in _FOLDED_PHRASES if rx.search(folded)]
    result = []
    for original, fp in hits:
        if any(fp != other_fp and fp in other_fp for _, other_fp in hits):
            continue  # dominated by a longer matched phrase in the same note
        result.append(original)
    return result


def scan_ground_truth(gt):
    """Yield (case_file, matched_phrase) for every flagged note in the GT. A
    non-object top-level (e.g. a JSON array) has no items and yields nothing
    rather than crashing on `.get`."""
    findings = []
    if not isinstance(gt, dict):
        return findings
    for i, item in enumerate(gt.get("items") or []):
        if not isinstance(item, dict):
            continue
        case = item.get("case_file") or ("items[%d]" % i)
        notes = item.get("notes")
        if not isinstance(notes, str) or not notes:
            notes = item.get("note")   # fall back on an empty/absent `notes`
        for phrase in scan_notes(notes if isinstance(notes, str) else ""):
            findings.append((case, phrase))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Advisory notes-lint: flag ground-truth notes that name "
                    "production/the code as the answer-key SOURCE (lỗ #1).")
    parser.add_argument("--ground-truth", required=True, help="path to ground_truth.json")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when anything is flagged (default is advisory exit 0)")
    args = parser.parse_args(argv)

    gt_path = Path(args.ground_truth)
    try:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print("ERROR: cannot read ground truth %s: %s" % (gt_path, e), file=sys.stderr)
        return 2

    findings = scan_ground_truth(gt)
    for case, phrase in findings:
        print("FLAG: %s: notes name the SOURCE as production/the code (%r) — "
              "derive the answer from spec, then cross-check; do not copy output"
              % (case, phrase))
    if not findings:
        print("OK: no source-indicator wording in ground-truth notes")
    else:
        print("WARNING: %d note(s) flagged — advisory, not a block; review each."
              % len(findings), file=sys.stderr)

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
