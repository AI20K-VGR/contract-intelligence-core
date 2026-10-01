"""Convert a human-labelled held-out CSV (one row per frame) into spike JSONL.

Held-out rows carry gold keys and an anchor (a short verbatim fragment that
identifies the frame), not hand-cut spans: they are scored with --mode llm-full.

Usage (repo root):
  ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.import_heldout \
      evals/spikes/clause_key/heldout.csv evals/spikes/clause_key/clauses_heldout.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evals.spikes.clause_key.mechanism import LEXICON_V1_PATH, fold, load_lexicon

FIELDS = [
    "clause_id", "profile", "text", "context_parties", "frame_type",
    "bearer", "action", "qualifier", "param", "object", "anchor",
    "consequence_type", "consequence_value", "note",
]
PROFILES = {"SALES", "SUPPLY_SERVICE", "LEASE", "CONSTRUCTION_WORK", "EMPLOYMENT", "NDA"}
CONSEQUENCE_TYPES = {
    "", "PENALTY_FIXED", "PENALTY_RATE", "INTEREST", "DAMAGES",
    "TERMINATION", "SUSPENSION", "WITHHOLD",
}


class HeldoutError(ValueError):
    pass


def _parties(raw: str, where: str, roles: set[str]) -> dict[str, str]:
    out = {}
    for part in filter(None, (p.strip() for p in raw.split(";"))):
        alias, _, role = part.partition("=")
        if role.strip() not in roles:
            raise HeldoutError(f"{where}: context_parties role '{role.strip()}' not in lexicon roles")
        out[alias.strip()] = role.strip()
    return out


def import_csv(path: Path, lexicon_path: Path = LEXICON_V1_PATH) -> list[dict]:
    lex = load_lexicon(lexicon_path)
    roles, actions = set(lex["roles"]), set(lex["actions"]) | {"NONE"}
    qualifiers, params = set(lex["qualifiers"]) | {""}, set(lex["parameters"]) | {"NONE"}

    clauses: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            row = {k: (v or "").strip() for k, v in row.items()}
            cid = row["clause_id"]
            where = f"line {n} ({cid})"
            if not cid:
                raise HeldoutError(f"{where}: clause_id is required")
            clause = clauses.get(cid)
            if clause is None:
                if row["profile"] not in PROFILES:
                    raise HeldoutError(f"{where}: profile '{row['profile']}' must be one of {sorted(PROFILES)}")
                if not row["text"]:
                    raise HeldoutError(f"{where}: text is required on the first row of a clause")
                clause = {"id": cid, "profile": row["profile"], "text": row["text"], "frames": []}
                parties = _parties(row["context_parties"], where, roles)
                if parties:
                    clause["context"] = {"parties": parties}
                clauses[cid] = clause

            anchor = row["anchor"]
            if not anchor or fold(anchor) not in fold(clause["text"]):
                raise HeldoutError(f"{where}: anchor must be a verbatim fragment of the clause text")
            if row["consequence_type"] not in CONSEQUENCE_TYPES:
                raise HeldoutError(f"{where}: consequence_type '{row['consequence_type']}' is not allowed")

            ftype = row["frame_type"]
            if ftype == "REMEDY":
                if row["action"] not in actions:
                    raise HeldoutError(f"{where}: action '{row['action']}' not in lexicon (or NONE)")
                if row["action"] != "NONE" and row["bearer"] not in roles:
                    raise HeldoutError(f"{where}: bearer '{row['bearer']}' not in lexicon roles")
                if row["qualifier"] not in qualifiers:
                    raise HeldoutError(f"{where}: qualifier '{row['qualifier']}' not in lexicon (or empty)")
                key = None if row["action"] == "NONE" else [row["bearer"], row["action"], row["qualifier"] or None]
            elif ftype == "PARAMETER":
                if row["param"] not in params:
                    raise HeldoutError(f"{where}: param '{row['param']}' not in lexicon (or NONE)")
                key = None if row["param"] == "NONE" else ["PARAM", row["param"], fold(row["object"]) or None]
            else:
                raise HeldoutError(f"{where}: frame_type must be REMEDY or PARAMETER")

            frame = {"frame_type": ftype, "gold_key": key, "anchor": anchor}
            if ftype == "REMEDY" and row["consequence_type"]:
                frame["gold_consequence"] = {
                    "type": row["consequence_type"],
                    "value": row["consequence_value"] or None,
                }
            if row["note"]:
                frame["note"] = row["note"]
            clause["frames"].append(frame)
    return list(clauses.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    clauses = import_csv(args.csv)
    with args.out.open("w", encoding="utf-8") as fh:
        for c in clauses:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    frames = sum(len(c["frames"]) for c in clauses)
    print(f"{len(clauses)} clauses, {frames} frames -> {args.out}")


if __name__ == "__main__":
    main()
