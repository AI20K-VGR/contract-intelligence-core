#!/usr/bin/env python3
"""validate_artifacts.py — a WARN-class checker that holds an artifact against
one of the JSON schemas in harness/schemas/.

Uses the real `jsonschema` library (declared OPTIONAL in preflight_deps.py) —
it auto-detects the draft from each schema's own `$schema` (draft-07 for
write-deny-policy.json, 2020-12 for the rest) and understands every keyword
those schemas actually use: type / required / enum / const / properties /
items, plus minimum / maximum / minItems / additionalProperties / pattern /
$ref / if-then / allOf. A prior hand-rolled slice only covered the first six —
narrow enough that three real broken artifacts (a value below its declared
minimum, an empty array where minItems forbade it, and a misspelled extra
field on a write-deny-policy record — additionalProperties: false is exactly
what should have caught that one) all passed it silently. That hand-rolled
path is gone rather than kept as a fallback: two checkers answering different
questions while both calling themselves "the schema check" is the same bug
this file exists to fix, just moved one level down.

Degradation when jsonschema is ABSENT (it is optional, so this must work on a
bare box): never claim clean. An empty-findings result is this file's only
way to say "valid", so the absent-dependency case returns one synthetic
finding naming the gap instead — same shape the coverage-floors gate uses for
an unmeasurable report (harness/scripts/coverage_gate.py): report the gap,
never a false pass.

It is advisory by design: validate() never raises and the CLI always exits 0,
emitting findings as JSON. A mismatch is a warning to a human, never a block —
the authoritative gate stays artifact_check.py.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def validate(schema: Any, artifact: Any) -> List[str]:
    """Hold `artifact` against `schema` via jsonschema, returning a list of WARN
    strings (one per mismatch); an empty list means clean. NEVER raises:
    - a non-dict schema yields no findings (nothing to assert against);
    - jsonschema absent, a broken schema, or any other internal failure
      yields ONE synthetic finding naming the gap — never an empty list,
      since empty is this function's only way to say "valid".
    """
    if not isinstance(schema, dict):
        return []

    try:
        import jsonschema
    except ImportError:
        return ["<validator>: jsonschema not installed — cannot validate this "
                "artifact; install it (see harness/scripts/preflight_deps.py) "
                "to enable real schema checking"]

    try:
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        errors = list(validator_cls(schema).iter_errors(artifact))
    except Exception as exc:  # noqa: BLE001 — WARN-class must never raise
        return ["<validator>: skipped a check (%s: %s)"
                % (type(exc).__name__, exc)]

    findings: List[str] = []
    for err in sorted(errors, key=lambda e: [str(p) for p in e.path]):
        path = ".".join(str(p) for p in err.path)
        findings.append("%s: %s" % (path or "<root>", err.message))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        description="WARN-class artifact validator (never blocks).")
    ap.add_argument("--schema", required=True,
                    help="path to a JSON schema in harness/schemas/")
    ap.add_argument("--artifact", required=True,
                    help="path to the JSON artifact to check")
    args = ap.parse_args()

    out: Dict[str, Any] = {"schema": args.schema, "artifact": args.artifact,
                           "findings": []}
    try:
        schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        out["findings"] = ["<schema>: could not load (%s)" % exc]
        print(json.dumps(out, ensure_ascii=False))
        return 0
    try:
        artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        out["findings"] = ["<artifact>: could not load (%s)" % exc]
        print(json.dumps(out, ensure_ascii=False))
        return 0

    out["findings"] = validate(schema, artifact)
    print(json.dumps(out, ensure_ascii=False))
    return 0  # WARN-class: advisory only, never blocks


if __name__ == "__main__":
    sys.exit(main())
