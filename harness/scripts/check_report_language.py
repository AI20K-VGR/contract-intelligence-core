"""check_report_language.py — advisory language + AI-tell checker for reports.

Reads a generated report, compares its detected language against the configured
output language (harness/data/output.yaml), and scans for the AI-writing tells
and Vietnamese translation tells named in
harness/data/output-styles/humanizer-and-anti-ai-tells.md.

Contract:
  - Advisory by default: exits 0, emits a PASS / PASS_WITH_RISK verdict on stdout,
    and never rewrites the report.
  - With --base-ref it adds diff-based blocking: a LANGUAGE MISMATCH on a file
    CHANGED vs the base ref escalates to BLOCKED and exits non-zero. Tells (dash,
    AI vocab, VN calque) stay advisory — they never block. Unchanged/legacy files
    and an unresolvable base ref stay warn-only (exit 0) so a shallow checkout
    never fails.
  - Findings carry a line number so a writer can locate the source. Evidence
    (file paths, IDs, quotes, fenced code) is reported by location, never mutated.

It complements the humanizer rule wired into the producer skills: the rule tells
the writer how to write; this checker is a cheap second pass that points at what
still reads translated or machine-made.
"""
import argparse
import json
import os
import re
import subprocess
import sys

# Vietnamese lowercase letters that carry a diacritic or are VN-specific.
_VI_CHARS = "àáâãèéêìíòóôõùúýăđĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
_VI_RE = re.compile("[" + _VI_CHARS + _VI_CHARS.upper() + "]")
_ALPHA_RE = re.compile(r"[A-Za-z" + _VI_CHARS + _VI_CHARS.upper() + "]")

# Non-prose tokens that carry letters but are NOT real words: counting them in the
# diacritic-ratio denominator dilutes a Vietnamese report that happens to be dense
# with English machinery (identifiers, paths, code spans) and misflags it as en.
# Order matters: strip code spans first, then path/identifier tokens, then the
# UPPERCASE verdict words harness reports lean on (PASS/BLOCKED/SKIP/…).
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
# A path or identifier is any run of word/dot/slash/dash chars that contains a
# slash, an underscore, or a dot — i.e. file paths and snake_case/dotted names.
# Plain words (no separator) are left intact so real prose still counts.
_PATH_OR_IDENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]*[/_.][A-Za-z0-9_./-]*")
# A bare snake_case-style call or identifier with a trailing paren, e.g. foo_bar().
_CALL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\(\)")
# All-caps tokens of two or more letters: PASS, BLOCKED, SKIP, PASS_WITH_RISK, …
_UPPER_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9_]+\b")


def _prose_only(text: str) -> str:
    """Strip non-prose tokens so only real words remain for language detection.

    Removes inline `code spans`, file paths and snake_case/dotted identifiers, bare
    foo() calls, and UPPERCASE verdict tokens (PASS/BLOCKED/SKIP). These carry Latin
    letters but no language signal, so leaving them in the denominator would dilute a
    Vietnamese report dense with English machinery down past the diacritic threshold
    and misdetect it as en. Each token is replaced by a space to keep word boundaries.
    """
    text = _INLINE_CODE_RE.sub(" ", text)
    text = _PATH_OR_IDENT_RE.sub(" ", text)
    text = _CALL_RE.sub(" ", text)
    text = _UPPER_TOKEN_RE.sub(" ", text)
    return text

# High-signal AI vocabulary (humanizer rule §1/§3/§5). Curated for precision:
# common technical words (rich, powerful, robust, key) are intentionally left out
# so the checker fires on clusters, not legitimate prose.
_AI_WORDS = (
    "delve", "leverage", "tapestry", "testament", "underscore", "underscores",
    "showcase", "showcases", "pivotal", "seamless", "groundbreaking", "boasts",
    "garner", "foster", "interplay", "intricate", "vibrant", "realm",
)
_AI_PHRASES = (
    "evolving landscape", "stands as a testament", "at its core",
    "without further ado", "let's dive in", "it's worth noting", "in today's",
)
_AI_WORD_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in _AI_WORDS) + r")\b", re.I)
_AI_PHRASE_RE = re.compile("|".join(re.escape(p) for p in _AI_PHRASES), re.I)
_DASH_RE = re.compile("[—–]")  # em dash / en dash — any hit is a tell

# Vietnamese translation tells (the "Đừng viết" column of the humanizer VN table).
_VI_TELLS = (
    "làm tươi", "quét tươi", "dữ liệu tươi", "đường gốc", "trải nghiệm gốc",
    "đảm bảo rằng", "đảm bảo là", "nhằm mục đích", "với mục đích", "một cách",
    "điều này cho phép", "việc này giúp", "đóng vai trò như", "hoạt động như",
    "tận dụng", "tối ưu hóa", "mạnh mẽ", "liền mạch", "toàn diện",
)


def detect_language(text: str) -> str:
    """vi when Vietnamese diacritics are a meaningful share of the REAL words, else en.

    Code spans, file paths, identifiers, and UPPERCASE verdict tokens are stripped
    first so they never dilute the ratio — a Vietnamese report dense with English
    machinery still reads as vi. English is the safe default: text with no real words
    (code/paths only) or no diacritics reads as en, so a plain English report never
    raises a false vi alarm.
    """
    words = _prose_only(text)
    alpha = len(_ALPHA_RE.findall(words))
    if not alpha:
        return "en"
    return "vi" if len(_VI_RE.findall(words)) / alpha >= 0.04 else "en"


def _scannable_lines(text: str):
    """Yield (line_number, line) for lines outside fenced code blocks.

    A banned word inside a ``` fence is a citation, not a tell, so the fence body
    is skipped entirely.
    """
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        # Fence detection: a line starting with ``` (after optional 0-3 space
        # indent per CommonMark) toggles the fence. Indented backticks in nested
        # code examples inside a fence are a known edge case — the detector may
        # toggle spuriously, potentially missing an AI tell in inline-documented
        # backtick examples. The humanizer pass catches the common cases.
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield i, line


def _find(text: str, expected: str):
    findings = []
    for ln, line in _scannable_lines(text):
        for m in _AI_WORD_RE.finditer(line):
            findings.append({"kind": "ai-vocab", "term": m.group(0).lower(), "line": ln})
        for m in _AI_PHRASE_RE.finditer(line):
            findings.append({"kind": "ai-phrase", "term": m.group(0).lower(), "line": ln})
        if _DASH_RE.search(line):
            findings.append({"kind": "dash", "term": "em/en dash", "line": ln})
        if expected == "vi":
            low = line.lower()
            for tell in _VI_TELLS:
                if tell in low:
                    findings.append({"kind": "vi-tell", "term": tell, "line": ln})
    return findings


def _resolve_base_ref(ref, cwd=None):
    """Resolve the diff base to a ref git can name here, or None when unavailable.

    The bare ``--base-ref`` flag arrives as ``__auto__`` and tries main then master;
    a named ref is verified as-is. None (no such ref, no repo, git missing) makes the
    caller degrade to warn-only. Fail-safe like loop_controller._git_diff_count: a
    severity probe must never raise.
    """
    candidates = ["main", "master"] if ref in (None, "__auto__") else [ref]
    for cand in candidates:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", cand],
                cwd=cwd, capture_output=True, text=True, timeout=10,
            )
        except Exception:  # noqa: BLE001 — git absent/timeout → warn-only
            return None
        if r.returncode == 0 and r.stdout.strip():
            return cand
    return None


def _changed_vs_base(path, base, cwd=None):
    """True/False if ``path`` differs from ``base``; None when git can't tell.

    "Changed" covers a modified tracked file, a staged-new file, and a brand-new
    untracked file — anything not identical to its state at ``base``. None on any git
    failure so the caller degrades to warn-only.
    """
    abspath = os.path.abspath(path)
    cwd = cwd or os.path.dirname(abspath) or "."
    try:
        d = subprocess.run(
            ["git", "diff", "--name-only", base, "--", abspath],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        if d.returncode != 0:
            return None
        if d.stdout.strip():
            return True
        o = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", abspath],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        if o.returncode != 0:
            return None
        return bool(o.stdout.strip())
    except Exception:  # noqa: BLE001 — git absent/timeout → warn-only
        return None


def check_report(path: str, expected: str, base_ref=None) -> dict:
    """Return a verdict dict for ``path`` against the ``expected`` language.

    Advisory by default (``base_ref=None``): verdict is PASS or PASS_WITH_RISK and the
    caller never blocks. With ``base_ref`` set, severity becomes diff-based — only a
    language mismatch on a file CHANGED vs that ref escalates to BLOCKED; tells stay
    advisory; an unchanged/legacy file stays a warning; an unresolvable ref degrades
    to warn-only.
    """
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        return {
            "tool": "check_report_language",
            "path": path,
            "verdict": "PASS",
            "skipped": "unreadable: %s" % exc.__class__.__name__,
        }

    # Detect the report's language from PROSE, not fenced code: a code block is
    # evidence (never translated), so counting it would dilute the diacritic ratio and
    # misflag a code-heavy vi report as en — which under --base-ref would BLOCK a
    # legitimate vi report. The tells pass already excludes fences; detection matches it.
    prose = "\n".join(line for _, line in _scannable_lines(text))
    detected = detect_language(prose)
    findings = _find(text, expected)
    match = detected == expected
    risk = (not match) or bool(findings)
    result = {
        "tool": "check_report_language",
        "path": path,
        "language_expected": expected,
        "language_detected": detected,
        "language_match": match,
        "verdict": "PASS_WITH_RISK" if risk else "PASS",
        "findings": findings,
        "summary": _summary(match, findings),
    }
    if base_ref is None:
        return result  # advisory default — contract unchanged

    # Diff-based severity: only a LANGUAGE MISMATCH on a file changed vs the base
    # ref blocks. Tells (dash / AI vocab / VN calque) are advisory — reported in
    # `findings` and reflected in PASS_WITH_RISK, but they never block, so an
    # internal report is not held to the cosmetic anti-AI bar.
    cwd = os.path.dirname(os.path.abspath(path)) or "."
    resolved = _resolve_base_ref(base_ref, cwd=cwd)
    changed = _changed_vs_base(path, resolved, cwd=cwd) if resolved else None
    blocking = bool(changed) and (not match)
    result["base_ref"] = resolved
    result["enforced"] = True
    result["changed"] = changed
    result["blocking"] = blocking
    if blocking:
        result["verdict"] = "BLOCKED"
    return result


def _summary(match: bool, findings) -> str:
    parts = []
    if not match:
        parts.append("language mismatch")
    if findings:
        parts.append("%d tell(s)" % len(findings))
    return "; ".join(parts) or "clean"


def _expected_language(arg):
    if arg in ("en", "vi"):
        return arg
    # Fall back to the configured output language; default vi if unreadable.
    try:
        from output_config import language
        return language()
    except Exception:
        return "vi"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Advisory language + AI-tell checker for a report.")
    ap.add_argument("path", help="report file to check")
    ap.add_argument("--expected", default=None,
                    help="expected language (en|vi); default = harness output config")
    ap.add_argument("--base-ref", nargs="?", const="__auto__", default=None,
                    help="enable diff-based blocking: a language mismatch on a file changed "
                         "vs this ref exits non-zero (tells stay advisory). Bare flag = main "
                         "then master; omit = advisory only.")
    args = ap.parse_args(argv)
    result = check_report(args.path, _expected_language(args.expected), base_ref=args.base_ref)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("blocking") else 0


if __name__ == "__main__":
    sys.exit(main())
