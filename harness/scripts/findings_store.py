#!/usr/bin/env python3
"""findings_store.py — durable belief store for hs:compound (append-only + replay-on-read).

hs:compound stops at Propose and writes nothing durable ("The report is the whole job"),
so run N+1 re-derives every belief from scratch. This adds a belief memory: a confidence
that seeds from the evidence source, decays with time, reinforces when the same idea
recurs, and surfaces for promotion once it is both confident and repeatedly evidenced.
The human still formalizes (Shape A) — the store only remembers, it never edits skills,
code, or config.

DEPARTURE from the source instinct_store: that store rewrites the whole file in place
(_atomic_rewrite) to update a confidence — which violates the harness append-only
discipline. Here NOTHING is ever rewritten or deleted. Confidence / decay / evidence are
recomputed AT READ time by replaying the records chronologically; the file only grows.

Records (machine-written JSON/JSONL, each carries actor + ts):
  observation {type, id, text, text_canon, category, conf_seed, source_ref, actor, ts}
  reinforce   {type, ref_id, delta_conf, actor, ts}

Read = recompute (read_beliefs). Per belief (an observation seed + the reinforce records
that name its id), confidence is replayed with decay INTERLEAVED between every pair of
events — a reinforce never erases decay already accrued:

    conf = conf_seed; evidence = 1; t_prev = ts(observation)
    for each reinforce at t_i:  conf *= exp(-LAMBDA * (t_i - t_prev))        # decay first
                                conf  = min(CEIL, conf + (1-conf)*delta)      # then reinforce
                                evidence += 1; t_prev = t_i
    finally:                    conf *= exp(-LAMBDA * (now - t_prev))         # decay to now

LAMBDA = 0.05/day; CONF_CEIL = 0.95 — no belief is "certain" before a human formalizes
it; a wrong-but-oft-repeated belief is caught at promote-review, not by conf reaching 1.0.

Dedup over the FULL set: find_similar scans EVERY belief ever seeded (Jaccard
>= 0.85 on text_canon), not the post-archive view. A recurring idea therefore always
emits a reinforce (reviving a faded belief through interleaved decay) instead of a
duplicate observation — one belief per idea, so a lens never over-counts. archive is a
READ-time view filter only (conf < 0.4 AND age >= 30d hides a belief from output; its
records stay in the file and stay dedup candidates).

CLI:
    findings_store.py --promote   surface promotion candidates (conf>=0.80 & evidence>=3)

Deferred (YAGNI): the store is append-only with no rotation, so read_beliefs is O(n)
replay. Empty store + single user => defer. Documented mitigation path (not built here):
a `--compact` that appends ONE baseline record snapshotting the replayed state, after
which read_beliefs starts from the latest baseline. Still append-only (no rewrite).
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from telemetry_paths import parse_iso_ts  # reuse the shared ISO-ts parser

# --- tunable knobs (single place) ---------------------------------------------
DECAY_LAMBDA = 0.05          # confidence decay per day
CONF_CEIL = 0.95             # a belief never reaches 1.0 before human formalization
ARCHIVE_CONF = 0.4           # below this AND old => archived from the read view
ARCHIVE_AGE_DAYS = 30
JACCARD_THRESHOLD = 0.85     # canon-token overlap that counts as the same idea
PROMOTE_CONF = 0.80
PROMOTE_EVIDENCE = 3
DEFAULT_DELTA_CONF = 0.15
CANON_MAX_TOKENS = 15        # text_canon is normalized to <=15 tokens for Jaccard

# Seed confidence by evidence source (source instinct_store: seed by provenance).
SEED_BY_SOURCE = {"telemetry": 0.7, "backlog": 0.5, "critic": 0.4}
DEFAULT_SEED = 0.4

# Tokens too common to carry meaning for the idea-equality check.
_STOPWORDS = frozenset(
    "a an the of to in on for and or but with without is are be been the this that these "
    "those it its as at by from into over under again more most some any".split())
_TOKEN_RE = re.compile(r"[a-z0-9]+")


# --- store path ---------------------------------------------------------------

def _default_path() -> Path:
    """harness/state/findings.jsonl, or HARNESS_FINDINGS_FILE when set (tests)."""
    env = os.environ.get("HARNESS_FINDINGS_FILE")
    if env:
        return Path(env)
    try:
        import harness_paths
        return harness_paths.state_dir() / "findings.jsonl"
    except Exception:
        # ABSOLUTE fallback (derived from this file's location) — a relative path would
        # resolve against the CWD and write to the wrong place if it changes mid-run.
        return Path(__file__).resolve().parent.parent / "state" / "findings.jsonl"


def _resolve(path) -> Path:
    return Path(path) if path is not None else _default_path()


# --- canon + similarity -------------------------------------------------------

def canon(text: str) -> str:
    """Normalize text to a <=15-token canon string for Jaccard: lowercased alphanumeric
    tokens, stopwords dropped, capped. The cap keeps a long proposal from drowning a
    short one in the union."""
    toks = [t for t in _TOKEN_RE.findall(str(text).lower()) if t not in _STOPWORDS]
    return " ".join(toks[:CANON_MAX_TOKENS])


def _tokset(canon_str: str) -> frozenset:
    return frozenset(canon_str.split())


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --- actor / append -----------------------------------------------------------

def _actor() -> str:
    try:
        hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
        if str(hooks_dir) not in sys.path:
            sys.path.append(str(hooks_dir))
        import hook_runtime
        return hook_runtime.resolve_actor()
    except Exception:
        return "user:unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(path: Path, record: dict) -> dict:
    """Append exactly one JSONL record. Append-ONLY: never read-modify-write. Serialize
    before opening so a non-serializable record never leaves a half-written line."""
    line = json.dumps(record, ensure_ascii=False) + "\n"
    p = Path(path)
    import harness_paths
    if harness_paths.data_root_unresolved(p.parent.parent):
        # Fail CLOSED here (unlike the telemetry hooks): a findings record is evidence,
        # so losing it silently is worse than refusing the write outright.
        raise ValueError(
            "refusing to append under the unresolved data root — no project resolved")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line)
    return record


# --- emit ---------------------------------------------------------------------

def emit_observation_record(text: str, category: str, source: str = "telemetry",
                            source_ref: Optional[str] = None, *, path=None,
                            actor: Optional[str] = None, ts: Optional[str] = None) -> dict:
    """Append a new observation (a freshly-seen belief). conf_seed is set by the
    evidence source. id is derived from canon+ts so a reinforce can name it."""
    p = _resolve(path)
    ts = ts or _now_iso()
    text_canon = canon(text)
    bid = hashlib.sha1(("%s|%s" % (text_canon, ts)).encode("utf-8")).hexdigest()[:12]
    rec = {
        "type": "observation",
        "id": bid,
        "text": str(text),
        "text_canon": text_canon,
        "category": str(category),
        "conf_seed": SEED_BY_SOURCE.get(source, DEFAULT_SEED),
        "source_ref": source_ref,
        "actor": actor or _actor(),
        "ts": ts,
    }
    return _append(p, rec)


def emit_reinforce(ref_id: str, delta_conf: float = DEFAULT_DELTA_CONF, *, path=None,
                   actor: Optional[str] = None, ts: Optional[str] = None) -> dict:
    """Append a reinforce naming an existing belief id (the same idea recurred)."""
    p = _resolve(path)
    rec = {
        "type": "reinforce",
        "ref_id": str(ref_id),
        "delta_conf": float(delta_conf),
        "actor": actor or _actor(),
        "ts": ts or _now_iso(),
    }
    return _append(p, rec)


def record_observation_or_reinforce(text: str, category: str, source: str = "telemetry",
                                    source_ref: Optional[str] = None, *, path=None,
                                    delta_conf: float = DEFAULT_DELTA_CONF,
                                    actor: Optional[str] = None, ts: Optional[str] = None) -> dict:
    """The caller-facing helper: if an equivalent belief already exists (Jaccard over the
    FULL seeded set, archived included), reinforce it; otherwise seed a new observation.
    This is what guarantees one-belief-per-idea."""
    hit = find_similar(text, path=path)
    if hit is not None:
        return emit_reinforce(hit["id"], delta_conf=delta_conf, path=path, actor=actor, ts=ts)
    return emit_observation_record(text, category, source=source, source_ref=source_ref,
                                   path=path, actor=actor, ts=ts)


# --- read = recompute ---------------------------------------------------------

def _read_records(path: Path) -> List[dict]:
    """Stream the store fail-soft: a missing file is empty; a corrupt or non-object line
    is skipped (never fatal). File order is chronological (append-only)."""
    p = Path(path)
    if not p.is_file():
        return []
    out: List[dict] = []
    try:
        fh = open(p, "r", encoding="utf-8", errors="replace")
    except OSError:
        return []
    with fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def _belief_from(obs: dict, reinforces: List[dict], now: datetime) -> dict:
    """Replay one belief's confidence with decay interleaved between events."""
    conf = float(obs.get("conf_seed", DEFAULT_SEED))
    t_prev = parse_iso_ts(obs.get("ts"))
    evidence = 1
    last_ts = t_prev
    # reinforces in chronological order by REAL instant (not ts string — a non-UTC offset
    # makes the lexical order disagree with real time); an unparseable ts sorts first and
    # is then skipped in the loop body.
    for r in sorted(reinforces,
                    key=lambda r: parse_iso_ts(r.get("ts")) or datetime.min.replace(tzinfo=timezone.utc)):
        t_i = parse_iso_ts(r.get("ts"))
        if t_i is None or t_prev is None:
            continue
        days = max(0.0, (t_i - t_prev).total_seconds() / 86400.0)
        conf *= math.exp(-DECAY_LAMBDA * days)
        conf = min(CONF_CEIL, conf + (1.0 - conf) * float(r.get("delta_conf", DEFAULT_DELTA_CONF)))
        evidence += 1
        t_prev = t_i
        last_ts = t_i
    if t_prev is not None and now is not None:
        days = max(0.0, (now - t_prev).total_seconds() / 86400.0)
        conf *= math.exp(-DECAY_LAMBDA * days)
    age_days = ((now - last_ts).total_seconds() / 86400.0) if (now and last_ts) else 0.0
    archived = conf < ARCHIVE_CONF and age_days >= ARCHIVE_AGE_DAYS
    return {
        "id": obs.get("id"),
        "text": obs.get("text"),
        "text_canon": obs.get("text_canon", canon(obs.get("text") or "")),
        "category": obs.get("category"),
        "conf": conf,
        "evidence": evidence,
        "source_ref": obs.get("source_ref"),
        "first_ts": obs.get("ts"),
        "last_ts": last_ts.isoformat() if last_ts else None,
        "archived": archived,
    }


def read_beliefs(now: Optional[datetime] = None, *, path=None,
                 include_archived: bool = False) -> List[dict]:
    """Replay every belief to `now`. By default an archived belief (faded + old) is
    filtered from the view; include_archived=True returns the full seeded set (the dedup
    candidate pool — archive is a view filter, not a deletion)."""
    if now is None:
        now = datetime.now(timezone.utc)
    records = _read_records(_resolve(path))
    observations = [r for r in records if r.get("type") == "observation" and r.get("id")]
    reinforces_by: Dict[str, List[dict]] = {}
    for r in records:
        if r.get("type") == "reinforce" and r.get("ref_id"):
            reinforces_by.setdefault(str(r["ref_id"]), []).append(r)
    beliefs = [_belief_from(o, reinforces_by.get(str(o["id"]), []), now) for o in observations]
    if include_archived:
        return beliefs
    return [b for b in beliefs if not b["archived"]]


def find_similar(text: str, *, path=None) -> Optional[dict]:
    """The existing belief whose canon is Jaccard >= threshold with `text`, scanning the
    FULL seeded set (archived included) so a recurrence reinforces/revives rather than
    duplicates. Returns the best match, or None."""
    target = _tokset(canon(text))
    if not target:
        # An empty canon (text was all stopwords / punctuation) carries no idea to dedup
        # on; _jaccard(empty, empty) is 1.0, so without this guard two DISTINCT contentless
        # texts would merge. A contentless belief never matches anything — seed it fresh.
        return None
    best, best_score = None, 0.0
    for b in read_beliefs(now=datetime.now(timezone.utc), path=path, include_archived=True):
        score = _jaccard(target, _tokset(b["text_canon"]))
        if score >= JACCARD_THRESHOLD and score > best_score:
            best, best_score = b, score
    return best


# --- promotion ----------------------------------------------------------------

def promotion_candidates(now: Optional[datetime] = None, *, path=None) -> List[dict]:
    """Beliefs that clear BOTH the confidence and evidence floors — surfaced for a human
    to formalize. Archived beliefs (faded) are not candidates."""
    beliefs = read_beliefs(now=now, path=path, include_archived=False)
    return [b for b in beliefs
            if b["conf"] >= PROMOTE_CONF and b["evidence"] >= PROMOTE_EVIDENCE]


# Suggested destination file per belief category (Shape A: a hint for the human, never an
# auto-write target). Extend as categories grow.
_CATEGORY_DEST = {
    "skills": "harness/plugins/hs/skills/",
    "telemetry": "harness/scripts/ (lens) / harness/data/observation-signals.yaml",
    "gates": "harness/hooks/ + harness/data/stage-policy.yaml",
    "docs": "docs/",
}


def _belief_view(b: dict) -> dict:
    return {"id": b["id"], "text": b["text"], "category": b["category"],
            "conf": round(b["conf"], 3), "evidence": b["evidence"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Durable belief store for hs:compound.")
    ap.add_argument("--promote", action="store_true",
                    help="surface promotion candidates (conf>=0.80 & evidence>=3); never writes")
    ap.add_argument("--list", action="store_true", dest="list_beliefs",
                    help="list current (non-archived) beliefs — read this at run start to avoid re-proposing")
    ap.add_argument("--emit", action="store_true",
                    help="record one belief (dedups: reinforce if equivalent exists, else seed)")
    ap.add_argument("--text", default=None, help="belief text (with --emit)")
    ap.add_argument("--category", default="misc", help="belief category (with --emit)")
    ap.add_argument("--source", default="critic", choices=sorted(SEED_BY_SOURCE),
                    help="evidence source -> conf_seed (with --emit)")
    ap.add_argument("--source-ref", default=None, help="evidence pointer, e.g. lens count / BACKLOG id")
    ap.add_argument("--path", default=None, help="store path (default: harness/state/findings.jsonl)")
    args = ap.parse_args(argv)

    if args.promote:
        cands = promotion_candidates(path=args.path)
        out = {
            "tool": "findings_store",
            "action": "promote",
            "note": "Shape A — surfaced for a human to formalize; nothing was written.",
            "candidates": [
                {**_belief_view(c),
                 "suggested_dest": _CATEGORY_DEST.get(c["category"], "(decide manually)")}
                for c in cands
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.list_beliefs:
        beliefs = read_beliefs(path=args.path)
        print(json.dumps({"tool": "findings_store", "action": "list",
                          "beliefs": [_belief_view(b) for b in beliefs]},
                         ensure_ascii=False, indent=2))
        return 0

    if args.emit:
        if not args.text:
            ap.error("--emit requires --text")
        rec = record_observation_or_reinforce(
            args.text, args.category, source=args.source,
            source_ref=args.source_ref, path=args.path)
        print(json.dumps({"tool": "findings_store", "action": "emit",
                          "recorded": rec["type"],
                          "ref_id": rec.get("ref_id") or rec.get("id")},
                         ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
