#!/usr/bin/env python3
"""analyze_telemetry.py — read-only CLI front for the telemetry lenses.

Deterministic gather + render; the LLM narrates the output. It NEVER judges — it
surfaces counts/rates/spans for a skill to adjudicate. READ-ONLY.

ADAPT note: the source corpus hard-imports its full lens set at module load. The
harness runs by REGISTRY instead (`LENS_REGISTRY`) and probes which rows import
(`available_lenses`) — the workflow lens ships now, and a new lens lands by
adding a row, never by editing this spine. A registry row whose module is absent
becomes a VISIBLE "absent" entry, never a silent drop.

Honesty gate: the markdown formatter ALWAYS emits a "NOT measured" section
enumerating what telemetry does not capture (unshipped lenses + intrinsic blind
spots) — a guard against reading partial telemetry as full coverage.

Usage:
  analyze_telemetry.py [--lens <name>|all] [--days N] [--top N] [--format md|json]

Env: HARNESS_STATE_DIR / HARNESS_SKILL_CHAINS / HARNESS_SKILLS_DIR redirect inputs.
"""

import argparse
import importlib
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from telemetry_formatters import json_output  # noqa: E402

# Lens registry: name → (module, gather(module, args)). The SINGLE extension
# point. The workflow lens ships now; analyze never hard-imports the full
# set — available_lenses() probes which rows actually import.
LENS_REGISTRY = {
    "workflow": ("lens_workflow_chains",
                 lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "skill_usage": ("lens_skill_usage",
                    lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "risk_flags": ("lens_risk_flags",
                   lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "reliability": ("lens_reliability",
                    lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "subagent_outcomes": ("lens_subagent_outcomes",
                          lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "observations": ("lens_observations",
                     lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "docs_build": ("lens_docs_build",
                   lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "perf_trend": ("lens_perf_trend",
                   lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "session": ("lens_session",
                lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "gate": ("lens_gate",
             lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "gemini": ("lens_gemini",
               lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
    "partner": ("lens_partner",
                lambda m, a: m.gather(days=a.days, top=(a.top or 10))),
}

# Order lenses appear in `--lens all`.
OVERVIEW_ORDER = ["workflow", "skill_usage", "risk_flags", "reliability",
                  "subagent_outcomes", "observations", "docs_build", "perf_trend",
                  "session", "gate", "gemini", "partner"]

# Dimensions telemetry deliberately does NOT capture — the honesty gate. Printed
# verbatim under "## NOT measured" so an output never reads as full coverage.
NOT_MEASURED = [
    "token / dollar cost per skill or session (not attributed)",
    "semantic correctness or quality of any run (only ran / coarse exit)",
    "wall-clock for non-script work (only harness/scripts & harness/e2e Bash runs are timed)",
    "human review depth or plan-approval quality",
    "lenses not yet shipped: health, validate, memory, product_memory "
    "(not yet shipped — the JSONL data is retained; the read-only lens is added "
    "later without touching this spine)",
]


def available_lenses() -> dict:
    """Registry rows whose module imports cleanly → {name: (module, gather_fn)}.
    A row whose module is absent is simply not returned (gather_all marks it
    absent for the render side)."""
    out = {}
    for name, (mod_name, fn) in LENS_REGISTRY.items():
        try:
            mod = importlib.import_module(mod_name)
        except Exception:  # noqa: BLE001
            # Any import-time failure (not just ImportError) drops the lens from
            # the registry; gather_all marks it absent rather than crashing the
            # read-only CLI for every other lens.
            continue
        out[name] = (mod, fn)
    return out


def _tag(agg, name):
    """Stamp the registry key on an aggregate so the render side can find the
    lens module's own render() — keeps render OUT of this spine (a new lens is a
    self-contained module: gather + render, zero spine edits)."""
    if isinstance(agg, dict):
        agg.setdefault("_lens_key", name)
    return agg


def gather_lens(name: str, args):
    avail = available_lenses()
    if name not in avail:
        return {"lens": name, "absent": True, "_lens_key": name}
    mod, fn = avail[name]
    try:
        return _tag(fn(mod, args), name)
    except Exception as e:  # noqa: BLE001 — isolate like gather_all: a lens that
        # raises (e.g. the workflow lens fail-loud on a missing data file) becomes
        # a VISIBLE error entry + exit 0, never a raw traceback on the single-lens
        # path. Read-only CLI: an unreadable lens must not crash the front-end.
        return {"lens": name, "error": "%s: %s" % (type(e).__name__, e), "_lens_key": name}


def gather_all(args) -> list:
    """Overview = every registry lens, each isolated. A lens raising (e.g. the
    workflow lens fail-loud when skill-chains.yaml is absent) must NOT blank the
    others — it degrades to a VISIBLE error entry, never a silent drop. A
    registry row whose module is absent becomes a VISIBLE 'absent' entry."""
    out = []
    avail = available_lenses()
    order = OVERVIEW_ORDER + [n for n in LENS_REGISTRY if n not in OVERVIEW_ORDER]
    for name in order:
        if name not in LENS_REGISTRY:
            continue
        if name not in avail:
            out.append({"lens": name, "absent": True, "_lens_key": name})
            continue
        mod, fn = avail[name]
        try:
            out.append(_tag(fn(mod, args), name))
        except Exception as e:  # noqa: BLE001 — one lens must not kill the overview
            out.append({"lens": name, "error": "%s: %s" % (type(e).__name__, e),
                        "_lens_key": name})
    return out


# --- render (each lens module owns its render(); the spine only dispatches) ---

def _render_one(agg: dict, avail: dict) -> str:
    name = agg.get("lens", "?")
    if agg.get("absent"):
        return "## lens: %s\n\n_not shipped in this build (registry row present, " \
               "module absent) — counted, never silently dropped_" % name
    if agg.get("error"):
        return "## lens: %s\n\n_error: %s_" % (name, agg["error"])
    # The lens module owns its render(), found via the registry key the gather
    # side stamped — so adding a lens never edits this spine. A lens with no
    # render() (or an untagged agg) falls back to JSON, never a crash.
    mod = avail.get(agg.get("_lens_key", ""), (None, None))[0]
    render = getattr(mod, "render", None)
    if callable(render):
        return render(agg)
    return "## lens: %s\n\n```json\n%s\n```" % (name, json_output(agg))


def _not_measured_block() -> str:
    return "## NOT measured\n\n" + \
        "\n".join("- %s" % t for t in NOT_MEASURED)


def render_md(data) -> str:
    aggregates = data if isinstance(data, list) else [data]
    # Resolve the registry ONCE — available_lenses() re-imports every module, and
    # the render loop called it per aggregate (O(N^2) imports). Pass it down.
    avail = available_lenses()
    parts = ["# Telemetry"]
    for agg in aggregates:
        parts.append(_render_one(agg, avail))
    parts.append(_not_measured_block())
    return "\n\n".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Telemetry lenses (read-only)")
    ap.add_argument("--lens", default="all",
                    help="lens name or 'all' (registered: %s)" % ", ".join(LENS_REGISTRY))
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, help="limit chains table to top N")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    if args.lens == "all":
        data = gather_all(args)
    elif args.lens in LENS_REGISTRY:
        data = gather_lens(args.lens, args)
    else:
        sys.stderr.write("unknown lens: %r; known: %s | all\n"
                         % (args.lens, ", ".join(LENS_REGISTRY)))
        return 2

    if args.format == "json":
        print(json_output(data))
    else:
        print(render_md(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
