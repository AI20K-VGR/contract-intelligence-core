#!/usr/bin/env python3
"""lens_gate.py — read-only lens over the gate trace.

Counts gate_pass / gate_block / gate_advisory / gate_skip across the trace, per hook
and per stage, with the top block/advisory reasons. This is the consumer that justifies
keeping the gate trace emission after the P7 local-unblock: `gate_advisory` is the
"how many times did a receipt gap slip past locally" signal personal-first needs —
local no longer blocks, but it still MEASURES.

Trace files (`harness/state/trace/trace-YYYYMMDD.jsonl`) are date-named and never
rotate, so the days filter is applied on the filename (bounded read). Fail-soft."""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hook_runtime  # noqa: E402
import telemetry_paths  # noqa: E402

_EVENTS = {"gate_pass", "gate_block", "gate_advisory", "gate_skip"}
_MIN_EVENTS = 5
_REASON_CAP = 80


def _trace_dir() -> Path:
    return hook_runtime._state_dir() / "trace"


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    by_event = Counter()
    by_stage = Counter()
    by_hook = Counter()
    block_reasons = Counter()
    advisory_reasons = Counter()
    total = 0
    d = _trace_dir()
    if d.is_dir():
        for f in sorted(d.glob("trace-*.jsonl")):
            # Parse the 8-char YYYYMMDD PREFIX so the --days filter fires for a
            # shard `trace-YYYYMMDD-<disc>.jsonl` too (its full stem is not
            # all-digits, so the old `.isdigit()` let every shard past the cutoff).
            date = f.stem[len("trace-"):len("trace-") + 8]
            if date.isdigit() and date < cutoff:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                ev = rec.get("event")
                if not isinstance(ev, str) or ev not in _EVENTS:
                    continue
                total += 1
                by_event[ev] += 1
                by_stage[str(rec.get("target") or "?")] += 1
                by_hook[str(rec.get("hook") or "?")] += 1
                note = str(rec.get("note") or "")[:_REASON_CAP]
                if ev == "gate_block" and note:
                    block_reasons[note] += 1
                elif ev == "gate_advisory" and note:
                    advisory_reasons[note] += 1
    return {
        "lens": "gate",
        "days": days,
        "total_events": total,
        "by_event": dict(by_event),
        "top_stages": [{"stage": k, "count": v} for k, v in by_stage.most_common(top)],
        "by_hook": dict(by_hook),
        "top_block_reasons": [{"reason": k, "count": v}
                              for k, v in block_reasons.most_common(top)],
        "top_advisory_reasons": [{"reason": k, "count": v}
                                 for k, v in advisory_reasons.most_common(top)],
        "sufficient": total >= _MIN_EVENTS,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_EVENTS),
    }


def render(agg) -> str:
    from telemetry_formatters import markdown_table
    head = "## lens: gate"
    be = agg.get("by_event", {})
    meta = ("_events: %s · pass: %s · block: %s · advisory: %s · skip: %s · gated: %s_"
            % (agg.get("total_events"), be.get("gate_pass", 0), be.get("gate_block", 0),
               be.get("gate_advisory", 0), be.get("gate_skip", 0), agg.get("gated")))
    rows = [[r["stage"], str(r["count"])] for r in agg.get("top_stages", [])]
    table = markdown_table(["stage", "events"], rows, align=["l", "r"])
    adv = agg.get("top_advisory_reasons", [])
    adv_block = ""
    if adv:
        adv_block = ("\n\n**Top advisory (receipt gaps that would gate on remote):**\n\n"
                     + "\n".join("- %s×%s" % (r["reason"], r["count"]) for r in adv))
    return "\n".join([head, meta, "", table]) + adv_block


if __name__ == "__main__":
    print(json.dumps(gather(days=int(sys.argv[1]) if len(sys.argv) > 1 else 30),
                     ensure_ascii=False, indent=2))
