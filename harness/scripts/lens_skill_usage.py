#!/usr/bin/env python3
"""lens_skill_usage.py — skill-invocation frequency from telemetry
invocations.jsonl: which skills are hot, and which HARNESS-OWNED (hs:*) skills
are never invoked in the window. Pure gather → render-agnostic dict. READ-ONLY.

"Never used" is only meaningful for owned skills: a vendored/third-party skill
sitting unused is expected, an hs:* skill nobody invokes is a trim candidate the
LLM can RAISE (never auto-remove). Fail-soft on telemetry (bad lines skipped);
the catalog read fails soft to an empty owned set rather than crashing the lens.
"""

import os
import sys
from collections import Counter

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402
from catalog import load_catalog, to_dir_id  # noqa: E402

_MIN_INVOCATIONS = 5  # below this the lens is low-volume gated (advice suppressed)
_REENABLE_MIN_SESSIONS = 3  # D2: distinct sessions demanding an off skill before a hint
_DEMAND_VIA = {"proxy_run", "router_block"}


def _norm_slug(skill: str) -> str:
    """A recorded demand identity → bare skill slug: 'hs:critique' / '/hs:ask' → 'critique'."""
    s = str(skill or "").strip().lstrip("/")
    if s.lower().startswith("hs:"):
        s = s[3:]
    return s.strip().lower()


def _reenable_candidates(days: int, root) -> list:
    """Off skills whose demand crosses the threshold, as re-enable candidates.

    Demand = rows written by the proxy/router for a skill that was off (via in
    _DEMAND_VIA). Counted as DISTINCT SESSIONS (D1) so a single spammy session cannot
    manufacture a signal. A candidate is surfaced only when it is STILL disabled (a
    since-re-enabled skill must not nag) and demand ≥ threshold (D2). Fail-soft."""
    sessions_by_slug: dict = {}
    for rec in telemetry_paths.iter_records_in_window("invocations.jsonl", days):
        if rec.get("via") not in _DEMAND_VIA:
            continue
        slug = _norm_slug(rec.get("skill", ""))
        if not slug:
            continue
        sessions_by_slug.setdefault(slug, set()).add(rec.get("session") or "")
    if not sessions_by_slug:
        return []
    try:
        import disabled_skills
        base = root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        from pathlib import Path
        sources = disabled_skills.default_sources(Path(base))
    except Exception:  # noqa: BLE001 — no disabled-state source → no candidates
        return []
    out = []
    for slug, sess in sessions_by_slug.items():
        n = len(sess)
        if n < _REENABLE_MIN_SESSIONS:
            continue
        try:
            if disabled_skills.status(slug, sources) != "disabled":
                continue  # live/unknown now → stale demand, do not surface
        except Exception:  # noqa: BLE001
            continue
        out.append({"skill": slug, "sessions": n})
    out.sort(key=lambda c: (-c["sessions"], c["skill"]))
    return out


def _counts_in_window(days: int, catalog: dict) -> Counter:
    # Shared read-path: dict-guarded, ts-windowed, non-object lines skipped.
    # Demand markers share this sink but are NOT tool-invocations — an off skill was
    # merely reached while off. Excluding them keeps top_skills / total_invocations /
    # the low-volume gate honest; the re-enable lens counts them separately.
    counts = Counter()
    for rec in telemetry_paths.iter_records_in_window("invocations.jsonl", days):
        if rec.get("via") in _DEMAND_VIA:
            continue
        skill = to_dir_id(rec.get("skill", ""), catalog)
        if skill:
            counts[skill] += 1
    return counts


def gather(days: int = 30, top: int = 10, skills_dir=None, root=None) -> dict:
    top = max(1, top)
    catalog = load_catalog(skills_dir)
    counts = _counts_in_window(days, catalog)
    total = sum(counts.values())
    owned = set(catalog.get("owned") or set())
    # Reliability is gauged over OWNED invocations only — a corpus dominated by
    # vendored/foreign skills must not flip the trim signal on, since it never
    # exercised the owned set.
    owned_total = sum(n for s, n in counts.items() if s in owned)
    never_used = sorted(owned - set(counts))
    # "Never used" is only a TRIM signal when the invocation corpus is dense
    # enough to have plausibly exercised every skill — at least one invocation
    # per owned skill on average. Below that, the list is dominated by skills
    # simply not yet observed (and the PreToolUse:Skill telemetry never sees a
    # skill run by hand), so presenting it as trim candidates is the exact
    # "sparse data → noise" the honesty gate exists to prevent.
    never_used_reliable = bool(owned) and owned_total >= len(owned)
    return {
        "lens": "skill_usage",
        "days": days,
        "total_invocations": total,
        "distinct_skills": len(counts),
        "top_skills": [{"skill": s, "count": n} for s, n in counts.most_common(top)],
        "owned_skills": len(owned),
        "never_used_owned": never_used,
        "never_used_reliable": never_used_reliable,
        "sufficient": total >= _MIN_INVOCATIONS,
        "min_invocations": _MIN_INVOCATIONS,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_INVOCATIONS),
        "reenable_candidates": _reenable_candidates(days, root),
        "reenable_min_sessions": _REENABLE_MIN_SESSIONS,
    }


def render(agg) -> str:
    """Markdown for this lens (owned here, not in the analyze_telemetry spine)."""
    from telemetry_formatters import markdown_table
    head = "## lens: skill_usage"
    meta = "_invocations: %s · distinct: %s · owned: %s · sufficient: %s · gated: %s_" % (
        agg.get("total_invocations"), agg.get("distinct_skills"),
        agg.get("owned_skills"), agg.get("sufficient"), agg.get("gated"))
    rows = [[r["skill"], str(r["count"])] for r in agg.get("top_skills", [])]
    table = markdown_table(["skill", "invocations"], rows, align=["l", "r"])
    never = agg.get("never_used_owned", [])
    never_block = ""
    if never and agg.get("never_used_reliable"):
        never_block = ("\n\n**Never invoked (owned hs:* — trim candidates, "
                       "advisory):**\n\n" + "\n".join("- %s" % s for s in never))
    elif never:
        never_block = (
            "\n\n_%d owned skill(s) had no invocation in the window, but only %s "
            "invocations were captured — too sparse to call them unused. "
            "PreToolUse:Skill telemetry only sees Skill-TOOL invocations, not "
            "skills run by hand, so non-use is NOT a trim signal here._"
            % (len(never), agg.get("total_invocations")))
    reenable = agg.get("reenable_candidates", [])
    reenable_block = ""
    if reenable:
        rows2 = ["- `%s` — %d session(s) reached it while off → "
                 "`hs-cli skills --enable %s`" % (c["skill"], c["sessions"], c["skill"])
                 for c in reenable]
        reenable_block = ("\n\n**Off skills in demand (≥%d distinct sessions — re-enable "
                          "candidates, advisory):**\n\n%s" % (
                              agg.get("reenable_min_sessions", _REENABLE_MIN_SESSIONS),
                              "\n".join(rows2)))
    return "%s\n\n%s\n\n%s%s%s" % (head, meta, table, never_block, reenable_block)
