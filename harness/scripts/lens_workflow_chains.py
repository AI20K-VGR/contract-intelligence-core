#!/usr/bin/env python3
"""lens_workflow_chains.py — actual per-session skill chains (telemetry
invocations.jsonl) vs the chains DECLARED in harness/data/skill-chains.yaml;
ranks common chains + flags deviations. PORT PS near-verbatim; env knob is
HARNESS_SKILL_CHAINS, sinks resolve through telemetry_paths.

The declared side reads an on-demand data file owned by the harness (not
always-on context); it fails LOUD when that file is missing or malformed —
a packaging/authoring bug must never read as "zero declared chains". The
actual side is fail-soft on telemetry data (bad lines skipped).

Pure gather → render-agnostic dict. READ-ONLY.
"""

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml_io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402
from catalog import load_catalog, to_dir_id  # noqa: E402


def _declared_chains_path() -> Path:
    """On-demand source of declared skill→skill chains. HARNESS_SKILL_CHAINS
    overrides so tests point at a fixture."""
    override = os.environ.get("HARNESS_SKILL_CHAINS")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "skill-chains.yaml"


def _parse_ts(raw):
    # Shared with the other read-side lenses (telemetry_paths.parse_iso_ts):
    # tz-naive normalized to UTC so a window-cutoff comparison never crashes.
    return telemetry_paths.parse_iso_ts(raw)


def actual_chains(days, catalog):
    by_session = defaultdict(list)
    # Shared read-path (dict-guarded, ts-windowed, non-object lines skipped); ts
    # is guaranteed in-window + parseable here, so it orders the session safely.
    for rec in telemetry_paths.iter_records_in_window("invocations.jsonl", days):
        skill = to_dir_id(rec.get("skill", ""), catalog)
        sess = rec.get("session", "")
        if not skill or not sess:
            continue
        by_session[sess].append((_parse_ts(rec.get("ts", "")), skill))
    chains = []
    for items in by_session.values():
        items.sort(key=lambda x: x[0])
        chains.append([s for _, s in items])
    return chains


def declared_chains(catalog):
    path = _declared_chains_path()
    if not path.exists():
        raise FileNotFoundError(
            "declared skill-chains data file missing: %s — the workflow-chains "
            "lens needs it; restore harness/data/skill-chains.yaml (it ships "
            "with the harness). A missing file here is a packaging bug, not "
            "zero chains." % path
        )
    data = yaml_io.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("chains")
    if raw is None:  # `chains:` absent/null → deliberately no declared chains
        return []
    if not isinstance(raw, list):
        raise ValueError("%s: 'chains' must be a list, got %s"
                         % (path, type(raw).__name__))
    out = []
    for chain in raw:
        # Fail loud on a malformed entry rather than silently char-splitting
        # a bare string or coercing null into a "None" step — silent
        # corruption is worse than a crash here.
        if not isinstance(chain, list):
            raise ValueError("%s: each chain must be a list of skill ids, "
                             "got %r" % (path, chain))
        steps = []
        for s in chain:
            if not isinstance(s, str) or not s.strip():
                raise ValueError("%s: chain step must be a non-empty string, "
                                 "got %r in %r" % (path, s, chain))
            steps.append(to_dir_id(s.strip().lstrip("/"), catalog))
        steps = [s for s in steps if s]  # drop ids not in catalog (coverage, not corruption)
        if len(steps) >= 2:
            out.append(steps)
    return out


def _norm(chain) -> str:
    return " → ".join(chain)


def gather(days: int = 30, top: int = 10, min_sessions: int = 5,
           skills_dir=None) -> dict:
    top = max(1, top)  # a negative/zero --top would empty most_common or tail-slice
    catalog = load_catalog(skills_dir)
    actual = actual_chains(days, catalog)
    declared = declared_chains(catalog)
    declared_set = {_norm(c) for c in declared}
    chain_freq = Counter(_norm(c) for c in actual if c)
    common = chain_freq.most_common(top)
    deviations = sorted(
        ((c, n) for c, n in chain_freq.items()
         if " → " in c and c not in declared_set),
        key=lambda x: -x[1],
    )
    # Formalization candidates: recurring UNDECLARED chains, scored by the part
    # of the cowork distil-formula the telemetry supports — frequency × steps
    # collapsed (a longer chain seen often is the strongest case to declare or
    # distil into a skill). Effort-saved and risk are NOT measurable from chain
    # data, so they are deliberately left out of the score rather than invented.
    candidates = sorted(
        ({"chain": c, "count": n, "steps": c.count(" → ") + 1,
          "score": n * (c.count(" → ") + 1)} for c, n in deviations),
        key=lambda d: (-d["score"], -d["count"], d["chain"]),
    )
    return {
        "lens": "workflow_chains",
        "days": days,
        "sessions_analyzed": len(actual),
        "sufficient": len(actual) >= min_sessions,
        "min_sessions": min_sessions,
        "common_chains": [{"chain": c, "count": n} for c, n in common],
        "declared_chains": [_norm(c) for c in declared],
        "deviations": [{"chain": c, "count": n} for c, n in deviations[:top]],
        "candidates": candidates[:top],
        "gated": telemetry_paths.low_volume_gate(len(actual), min_sessions),
    }


def render(agg) -> str:
    """Markdown for this lens (owned here so adding a lens never edits the
    analyze_telemetry spine). A 1-count deviation on a gated corpus is caveated,
    not presented as a finding."""
    from telemetry_formatters import markdown_table
    head = "## lens: workflow_chains"
    meta = "_sessions analyzed: %s · sufficient: %s · gated: %s_" % (
        agg.get("sessions_analyzed"), agg.get("sufficient"), agg.get("gated"))
    rows = [[c["chain"], str(c["count"])] for c in agg.get("common_chains", [])]
    table = markdown_table(["chain", "count"], rows, align=["l", "r"])
    devs = agg.get("deviations", [])
    dev_block = ""
    if devs and agg.get("gated"):
        dev_block = ("\n\n_%d undeclared chain(s) observed, but the session "
                     "corpus is too sparse (gated) to call them deviations — "
                     "not presented as findings._" % len(devs))
    elif devs:
        dev_rows = [[d["chain"], str(d["count"])] for d in devs]
        dev_block = "\n\n**Deviations (undeclared chains):**\n\n" + \
            markdown_table(["chain", "count"], dev_rows, align=["l", "r"])
    # Formalization candidates: only surfaced when the corpus is NOT gated — a
    # candidate distilled from one or two sessions would be noise dressed as a
    # recommendation. The score is frequency × steps (see gather()).
    cands = agg.get("candidates", [])
    cand_block = ""
    if cands and not agg.get("gated"):
        cand_rows = [[c["chain"], str(c["count"]), str(c["steps"]),
                      str(c["score"])] for c in cands]
        cand_block = ("\n\n**Formalization candidates** "
                      "(recurring undeclared workflows — declare in "
                      "`skill-chains.yaml` or distil into a skill; "
                      "score = frequency × steps):\n\n" +
                      markdown_table(["chain", "seen", "steps", "score"],
                                     cand_rows, align=["l", "r", "r", "r"]))
    return "%s\n\n%s\n\n%s%s%s" % (head, meta, table, dev_block, cand_block)
