#!/usr/bin/env python3
"""eval_config.py — persist an approved strategy card as canonical JSON + sha256.

A strategy card the user has approved must not live only in the conversation
(L4/card-hash lock): `write` validates the card's SHAPE (reusing
eval_scaffold's judgment-field validators for the fields the two scripts
share, plus this script's own for case_matrix/epsilon/approval provenance),
then persists it as `<target>/evals/eval_config.json` (canonical
`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`)
and a `eval_config.sha256` sidecar (hex digest of the JSON file's bytes).
Every later turn runs `verify` first: re-hash and compare, refuse to proceed
on a mismatch.

Honesty note (read before trusting this as a security control): this is a
tamper-EVIDENT presence gate, NOT tamper-proof. Editing both files together
by hand still passes physically — the value is catching accidental drift or
a single-file edit, plus the git diff in the target repo making any change
visible. This never claims to stop deliberate fraud.

Stdlib only; paths resolve off __file__; never imports harness/scripts/ (this
skill is self-contained, same discipline as eval_scaffold.py). Reuses
eval_scaffold's validators via a sibling import, not a package import — see
`_load_eval_scaffold` below.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_scaffold  # noqa: E402  (sibling import — see module docstring)


_KNOWN_SURFACES = ("extraction", "generation", "classification", "retrieval")
_KNOWN_FORGES = ("github", "gitlab")

_KNOWN_FIELDS = frozenset((
    "schema_version", "domain", "strategy", "surface", "production_module",
    "production_entry", "mirror_lang", "mirror_invoke", "forge", "threshold",
    "p0_rules", "dimensions", "primary_dimension", "judge_model", "pipeline_model",
    "domain_config", "case_matrix", "epsilon", "cited_lessons", "approved_by",
    "approved_ts", "code_mutations",
))

# the id is interpolated into a temp path (code-<id>/) by the runner, so it must
# be a path-safe token: no separators, no leading dot (blocks "..").
_CODE_MUTATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CODE_MUTATION_TARGETS = ("pipeline_mirror", "check_p0_gates")
_CODE_MUTATION_PATCH_KINDS = ("symbol_return", "regex_sub")
_SYMBOL_RETURN_SYMBOLS = ("run_pipeline", "check_p0_gates")

# Loose ISO-8601: date required, time/offset optional — "looking like" is the
# bar (§ phase spec), not full RFC-3339 parsing.
_ISO_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$")


def _require(card: dict, field: str):
    if field not in card:
        raise ValueError("%s: missing required field" % field)
    return card[field]


def _require_nonempty_str(card: dict, field: str) -> str:
    value = _require(card, field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s: must be a non-empty string" % field)
    return value


def _is_finite_json_value(value) -> bool:
    """True unless the value contains a non-finite float (NaN/Infinity), checked
    recursively through lists and dict values. json.loads accepts NaN/Infinity
    by default, so a card can carry one; this catches it before it reaches the
    source-patch repr()."""
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_finite_json_value(v) for v in value)
    if isinstance(value, dict):
        return all(_is_finite_json_value(v) for v in value.values())
    return True


def _validate_code_mutations(card) -> None:
    """Validate the OPTIONAL `code_mutations` list — DP-2 code-vehicle patch
    points a reviewer approved at R7. SHAPE only (deterministic), same error
    voice as the rest of validate_card. Absent field -> back-compat no-op.

    symbol_return is the primary kind (name-anchored: patches a fixed template
    symbol, so the card can be hashed at R7 before the mirror/scorer are
    filled). regex_sub is content-anchored -> only a stderr warning that the
    card must be re-hashed after the fill; not a hard failure."""
    muts = card.get("code_mutations")
    if muts is None:
        return
    if not isinstance(muts, list):
        raise ValueError("code_mutations: must be a list when present")

    seen_ids = set()
    for i, entry in enumerate(muts):
        if not isinstance(entry, dict):
            raise ValueError("code_mutations[%d]: must be an object" % i)

        mid = entry.get("id")
        if not isinstance(mid, str) or not mid.strip():
            raise ValueError("code_mutations[%d].id: must be a non-empty string" % i)
        if not _CODE_MUTATION_ID_RE.match(mid):
            raise ValueError(
                "code_mutations[%d].id: %r must be a path-safe token "
                "([A-Za-z0-9][A-Za-z0-9._-]*) — it is used in a filesystem path" % (i, mid))
        if mid in seen_ids:
            raise ValueError("code_mutations[%d].id: %r is duplicated (must be unique)" % (i, mid))
        seen_ids.add(mid)

        target = entry.get("target")
        if target not in _CODE_MUTATION_TARGETS:
            raise ValueError(
                "code_mutations[%d].target: %r must be one of %s"
                % (i, target, ", ".join(_CODE_MUTATION_TARGETS)))

        patch = entry.get("patch")
        if not isinstance(patch, dict):
            raise ValueError("code_mutations[%d].patch: must be an object" % i)
        kind = patch.get("kind")
        if kind not in _CODE_MUTATION_PATCH_KINDS:
            raise ValueError(
                "code_mutations[%d].patch.kind: %r must be one of %s"
                % (i, kind, ", ".join(_CODE_MUTATION_PATCH_KINDS)))
        if kind == "symbol_return":
            symbol = patch.get("symbol")
            if symbol not in _SYMBOL_RETURN_SYMBOLS:
                raise ValueError(
                    "code_mutations[%d].patch.symbol: %r must be one of %s"
                    % (i, symbol, ", ".join(_SYMBOL_RETURN_SYMBOLS)))
            # `value` becomes `return <value>` in the patched source via
            # repr()->ast. A non-finite float (NaN/Infinity) reprs to a bare
            # name (nan/inf) that NameErrors at run time — the crash would exit
            # 1 and be misread as a gate verdict. Reject it here.
            if not _is_finite_json_value(patch.get("value")):
                raise ValueError(
                    "code_mutations[%d].patch.value: must be a finite JSON value "
                    "(no NaN/Infinity)" % i)
        elif kind == "regex_sub":
            # regex_sub is content-anchored; a card missing anchor/replacement
            # (or a non-int count) would crash at run time (KeyError/TypeError)
            # and exit 1 — a false gate verdict. Validate the shape now.
            anchor = patch.get("anchor")
            if not isinstance(anchor, str) or not anchor:
                raise ValueError(
                    "code_mutations[%d].patch.anchor: regex_sub requires a non-empty string" % i)
            replacement = patch.get("replacement")
            if not isinstance(replacement, str):
                raise ValueError(
                    "code_mutations[%d].patch.replacement: regex_sub requires a string" % i)
            try:
                re.compile(anchor)
            except re.error as e:
                raise ValueError(
                    "code_mutations[%d].patch.anchor: not a valid regex pattern (%s)" % (i, e))
            # An invalid replacement backreference (e.g. \9 with no such group)
            # only raises at substitution time; it is NOT caught here. That is
            # deliberate — the runner classes any run-time re.error as a setup
            # error (exit 2, _SETUP_ERRORS), so it never leaks as a gate verdict.
            count = patch.get("count", 1)
            if not isinstance(count, int) or isinstance(count, bool):
                raise ValueError(
                    "code_mutations[%d].patch.count: must be an int" % i)
            print(
                "WARNING: code_mutations[%d] uses patch.kind 'regex_sub' (content-anchored) "
                "— re-hash the card after the mirror/scorer fill (re-run `write`)" % i,
                file=sys.stderr)

        expected_exit = entry.get("expected_exit", 1)
        if not isinstance(expected_exit, int) or isinstance(expected_exit, bool):
            raise ValueError("code_mutations[%d].expected_exit: must be an int" % i)


def validate_card(card) -> None:
    """Validate the card's SHAPE only (type/presence/membership) — never a
    coverage or "is this a good rule" judgment (that is the mutation matrix's
    job). Every
    judgment VALUE still comes solely from the approved card; this function
    only refuses a malformed one. Raises ValueError naming the bad field."""
    if not isinstance(card, dict):
        raise ValueError("card: must be a JSON object")

    _require_nonempty_str(card, "schema_version")
    domain = _require_nonempty_str(card, "domain")
    eval_scaffold._validate_token("domain", domain)

    strategy = _require_nonempty_str(card, "strategy")
    if strategy not in eval_scaffold.STRATEGIES:
        raise ValueError(
            "strategy: %r must be one of %s" % (strategy, ", ".join(eval_scaffold.STRATEGIES)))

    surface = _require_nonempty_str(card, "surface")
    if surface not in _KNOWN_SURFACES:
        raise ValueError("surface: %r must be one of %s" % (surface, ", ".join(_KNOWN_SURFACES)))

    production_module = _require_nonempty_str(card, "production_module")
    eval_scaffold._validate_module_path(production_module)
    _require_nonempty_str(card, "production_entry")
    _require_nonempty_str(card, "mirror_lang")

    mirror_invoke = card.get("mirror_invoke")
    if mirror_invoke is not None:
        argv_template = mirror_invoke.get("argv_template") if isinstance(mirror_invoke, dict) else None
        if (not isinstance(mirror_invoke, dict) or set(mirror_invoke) != {"argv_template"}
                or not isinstance(argv_template, list)
                or not all(isinstance(a, str) for a in argv_template)):
            raise ValueError(
                'mirror_invoke: when present must be exactly {"argv_template": [str, ...]}')

    forge = _require_nonempty_str(card, "forge")
    if forge not in _KNOWN_FORGES:
        raise ValueError("forge: %r must be one of %s" % (forge, ", ".join(_KNOWN_FORGES)))

    threshold = _require(card, "threshold")
    if not isinstance(threshold, int) or isinstance(threshold, bool):
        raise ValueError("threshold: must be an int, got %r" % (threshold,))
    if not (0 <= threshold <= 100):
        raise ValueError("threshold: must be within 0..100, got %d" % threshold)

    p0_rules = _require(card, "p0_rules")
    if not isinstance(p0_rules, list) or not p0_rules:
        raise ValueError("p0_rules: must be a non-empty list of rule objects")
    for i, rule in enumerate(p0_rules):
        if not isinstance(rule, dict):
            raise ValueError("p0_rules[%d]: must be an object" % i)
        if not isinstance(rule.get("rule"), str) or not rule["rule"].strip():
            raise ValueError("p0_rules[%d].rule: must be a non-empty string" % i)
        if not isinstance(rule.get("source"), str) or not rule["source"].strip():
            raise ValueError("p0_rules[%d].source: must be a non-empty string" % i)
        target_axis = rule.get("target_axis")
        if target_axis is not None and not isinstance(target_axis, str):
            raise ValueError("p0_rules[%d].target_axis: must be a string or null" % i)

    dimensions = _require(card, "dimensions")
    eval_scaffold._validate_dimensions(dimensions)
    primary_dimension = _require_nonempty_str(card, "primary_dimension")
    if primary_dimension not in dimensions:
        raise ValueError(
            "primary_dimension: %r must be one of dimensions %s"
            % (primary_dimension, sorted(dimensions)))

    judge_model = card.get("judge_model")
    pipeline_model = card.get("pipeline_model")
    if strategy in ("judge", "hybrid") and (judge_model is None or pipeline_model is None):
        raise ValueError("judge_model: strategy %r requires BOTH judge_model and pipeline_model"
                         % strategy)
    if judge_model is not None and (not isinstance(judge_model, str) or not judge_model.strip()):
        raise ValueError("judge_model: must be a non-empty string or null")
    if pipeline_model is not None and (not isinstance(pipeline_model, str) or not pipeline_model.strip()):
        raise ValueError("pipeline_model: must be a non-empty string or null")
    if judge_model is not None and pipeline_model is not None and judge_model == pipeline_model:
        raise ValueError("judge_model/pipeline_model: must differ (R8 self-eval guard)")

    domain_config = _require(card, "domain_config")
    eval_scaffold._validate_domain_config(domain_config)

    case_matrix = _require(card, "case_matrix")
    if not isinstance(case_matrix, list) or not case_matrix:
        raise ValueError("case_matrix: must be a non-empty list of cases")
    for i, case in enumerate(case_matrix):
        if not isinstance(case, dict):
            raise ValueError("case_matrix[%d]: must be an object" % i)
        for field in ("case", "input", "expect"):
            if field not in case:
                raise ValueError("case_matrix[%d].%s: missing required field" % (i, field))
        mutations = case.get("mutations")
        if mutations is not None and not isinstance(mutations, list):
            raise ValueError("case_matrix[%d].mutations: must be a list when present" % i)

    epsilon = _require(card, "epsilon")
    if not isinstance(epsilon, dict):
        raise ValueError("epsilon: must be an object")
    allowed_epsilon_keys = set(dimensions) | {"maturity"}
    for key, value in epsilon.items():
        if key not in allowed_epsilon_keys:
            raise ValueError(
                "epsilon.%s: key must be one of dimensions or \"maturity\"" % key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("epsilon.%s: must be a number" % key)
    if "maturity" not in epsilon:
        # every card has a threshold gate, so the maturity band is never optional —
        # a card that slips through without it fails later at the mutation
        # matrix (unkillable mutation) instead of here; close it at the source.
        raise ValueError(
            "epsilon.maturity: required — every card has a threshold, so epsilon "
            "must define the maturity band")

    cited_lessons = _require(card, "cited_lessons")
    if not isinstance(cited_lessons, list):
        raise ValueError("cited_lessons: must be a list")

    _require_nonempty_str(card, "approved_by")
    approved_ts = _require_nonempty_str(card, "approved_ts")
    if not _ISO_TS_RE.match(approved_ts):
        raise ValueError("approved_ts: must look like an ISO-8601 timestamp, got %r" % approved_ts)

    _validate_code_mutations(card)

    for key in card:
        if key not in _KNOWN_FIELDS:
            print("WARNING: unknown card field %r (forward-tolerant, ignored)" % key,
                  file=sys.stderr)


def _atomic_write(path: Path, data: bytes) -> None:
    """tmp-in-same-dir + fsync + os.replace — copied from artifact_io.py:58-71
    (copy-not-import: this skill stays stdlib-only and never imports
    harness/scripts/). A crash mid-write leaves the destination untouched (the
    tmp never got renamed) and the tmp itself is unlinked on any failure."""
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _card_paths(target: str):
    evals_dir = Path(target) / "evals"
    return evals_dir, evals_dir / "eval_config.json", evals_dir / "eval_config.sha256"


def cmd_write(target: str, card_source: str) -> int:
    try:
        raw = sys.stdin.read() if card_source == "-" else Path(card_source).read_text(encoding="utf-8")
    except OSError as e:
        print("ERROR: cannot read card %s: %s" % (card_source, e), file=sys.stderr)
        return 2

    try:
        card = json.loads(raw)
    except json.JSONDecodeError as e:
        print("ERROR: invalid card JSON: %s" % e, file=sys.stderr)
        return 2

    try:
        validate_card(card)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    if eval_scaffold.is_self_target(target):
        print(
            "ERROR: self-target fence: %r is the harness/orchestrator repo that hosts "
            "this skill — refusing to write eval_config into it." % target, file=sys.stderr)
        return 2

    evals_dir, json_path, sha_path = _card_paths(target)
    evals_dir.mkdir(parents=True, exist_ok=True)

    body = json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    body_bytes = body.encode("utf-8")
    digest = hashlib.sha256(body_bytes).hexdigest() + "\n"

    try:
        _atomic_write(json_path, body_bytes)
        _atomic_write(sha_path, digest.encode("utf-8"))
    except OSError as e:
        print("ERROR: write failed: %s" % e, file=sys.stderr)
        return 2

    print("wrote %s" % json_path)
    return 0


def _verify_and_load(target: str):
    """Hash-check the card pair and return (rc, card_or_None).

    Shared by `verify` and `emit-mirror-contract`: any consumer of the card's
    contents must go through this same check first (the card-hash governance
    — a contract derived from a drifted card would silently ship a stale
    invoke/schema). rc mirrors the historical `verify` contract exactly:
    0 = matches, 1 = hash mismatch, 2 = missing/unreadable pair.
    """
    _, json_path, sha_path = _card_paths(target)
    if not json_path.is_file() or not sha_path.is_file():
        print("ERROR: missing eval_config.json or eval_config.sha256 under %s"
              % json_path.parent, file=sys.stderr)
        return 2, None

    body = json_path.read_bytes()
    try:
        card = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print("ERROR: eval_config.json is not valid JSON: %s" % e, file=sys.stderr)
        return 2, None

    expected = sha_path.read_text(encoding="utf-8").strip()
    actual = hashlib.sha256(body).hexdigest()
    if expected != actual:
        print("ERROR: hash mismatch: expected=%s actual=%s" % (expected, actual), file=sys.stderr)
        return 1, None

    return 0, card


def cmd_verify(target: str) -> int:
    rc, _card = _verify_and_load(target)
    if rc == 0:
        print("OK: eval_config.json matches eval_config.sha256")
    return rc


def cmd_show(target: str, p0_line: bool) -> int:
    _, json_path, _sha = _card_paths(target)
    if not json_path.is_file():
        print("ERROR: no eval_config.json under %s" % json_path.parent, file=sys.stderr)
        return 2
    try:
        card = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print("ERROR: eval_config.json is not valid JSON: %s" % e, file=sys.stderr)
        return 2

    if p0_line:
        print("; ".join(r["rule"] for r in card.get("p0_rules") or []))
    else:
        print(json.dumps(card, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def cmd_hash(target: str) -> int:
    _, _json, sha_path = _card_paths(target)
    if not sha_path.is_file():
        print("ERROR: no eval_config.sha256 under %s" % sha_path.parent, file=sys.stderr)
        return 2
    print(sha_path.read_text(encoding="utf-8").strip())
    return 0


# --- mirror_contract.json (emit-mirror-contract) -----------------------------
#
# The subprocess contract for the mirror runner is not chosen from a
# catalog — code SYNTHESIZES it from the already-approved card. The only
# judgment values here (which lang, what entry) already live on the card
# (mirror_lang, production_entry, the optional mirror_invoke override); this
# table is a MECHANICAL convenience for the handful of interpreters common
# enough to not need a card-level declaration — it is deterministic rendering
# of "how do you normally run a <lang> file", same spirit as the sha256
# governance render, never a stand-in for a real judgment call. A lang NOT in
# this table has no mechanical default: the card MUST carry `mirror_invoke`
# (validated by validate_card already) or emission refuses (R7 — go back and
# approve a card that declares it).
_LANG_INVOKE = {
    "python": ["python3", "{mirror_path}"],
    "node": ["node", "{mirror_path}"],
    "javascript": ["node", "{mirror_path}"],
    "go": ["go", "run", "{mirror_path}"],
    "ruby": ["ruby", "{mirror_path}"],
    "php": ["php", "{mirror_path}"],
    "bash": ["bash", "{mirror_path}"],
    "sh": ["sh", "{mirror_path}"],
}

# lang -> mirror_filename extension (mirror_filename is mandatory on
# every contract, including a card-declared lang outside _LANG_INVOKE — the
# fallback below reuses the lang token itself as the extension, which is
# mechanical (a direct rendering of the card's own `mirror_lang` string), not
# a second judgment call).
_LANG_EXT = {
    "python": "py",
    "node": "js",
    "javascript": "js",
    "go": "go",
    "ruby": "rb",
    "php": "php",
    "bash": "sh",
    "sh": "sh",
}

_LANG_TOKEN_RE = re.compile(r"^[a-z0-9_+-]+$")


def _mirror_ext(lang: str) -> str:
    ext = _LANG_EXT.get(lang)
    if ext is not None:
        return ext
    # mechanical fallback for a lang outside the built-in table: reuse the
    # card's own token verbatim as the extension (no code-side guessing of
    # WHAT the extension "should" be — it is literally the card's value).
    lowered = lang.lower()
    return lowered if _LANG_TOKEN_RE.match(lowered) else "mirror"


def _resolve_argv_template(card: dict):
    """Return (argv_template, error_message_or_None).

    Card-declared `mirror_invoke` always wins when present (an explicit
    per-card override of the built-in table, per the phase design). Absent
    that, fall back to the built-in table; a lang in neither has no
    mechanical value to fall back to, so this refuses rather than guess.
    """
    mirror_invoke = card.get("mirror_invoke")
    if mirror_invoke is not None:
        return mirror_invoke["argv_template"], None

    lang = card["mirror_lang"]
    argv_template = _LANG_INVOKE.get(lang)
    if argv_template is not None:
        return argv_template, None

    return None, (
        "mirror_lang %r has no built-in invoke template; declare "
        "mirror_invoke on the card (re-approve via the R7 gate) with "
        '{"argv_template": [...]} and re-run write' % lang)


def _output_schema_keys(card: dict):
    """Sorted union of field names appearing in every case_matrix `expect`
    object — deterministic derivation, no judgment (the phase spec: "union
    field names in case_matrix expects")."""
    keys = set()
    for case in card["case_matrix"]:
        expect = case.get("expect")
        if isinstance(expect, dict):
            keys.update(expect.keys())
    return sorted(keys)


def cmd_emit_mirror_contract(target: str) -> int:
    rc, card = _verify_and_load(target)
    if rc != 0:
        return rc

    lang = card["mirror_lang"]
    argv_template, err = _resolve_argv_template(card)
    if err is not None:
        print("ERROR: %s" % err, file=sys.stderr)
        return 2

    domain = card["domain"]
    _, _json_path, sha_path = _card_paths(target)
    card_hash = "sha256:" + sha_path.read_text(encoding="utf-8").strip()

    contract = {
        "schema_version": "1.0",
        "card_hash": card_hash,
        "lang": lang,
        "mirror_filename": "pipeline_mirror.%s" % _mirror_ext(lang),
        "invoke": {
            "argv_template": list(argv_template),
            "input": "arg-file-utf8",
            "output": "stdout-json-utf8",
        },
        "entry_semantics": "one case input on stdin/arg-file -> ONE JSON object on stdout",
        "output_schema": {
            "type": "object",
            "keys_from_dimensions_and_cases": _output_schema_keys(card),
        },
        "timeout_seconds": 10,
        "zero_network": True,
        "deterministic": True,
    }

    contract_dir = Path(target) / "evals" / "eval_types" / domain
    contract_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"

    try:
        _atomic_write(contract_dir / "mirror_contract.json", body.encode("utf-8"))
    except OSError as e:
        print("ERROR: write failed: %s" % e, file=sys.stderr)
        return 2

    print("wrote %s" % (contract_dir / "mirror_contract.json"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Persist an approved eval strategy card as canonical JSON + sha256 "
                    "(tamper-evident presence gate, not tamper-proof)")
    sub = parser.add_subparsers(dest="verb", required=True)

    p_write = sub.add_parser("write")
    p_write.add_argument("--target", required=True)
    p_write.add_argument("--card", required=True, help='path to card JSON, or "-" for stdin')

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--target", required=True)

    p_show = sub.add_parser("show")
    p_show.add_argument("--target", required=True)
    p_show.add_argument("--p0-line", action="store_true")

    p_hash = sub.add_parser("hash")
    p_hash.add_argument("--target", required=True)

    p_emit = sub.add_parser("emit-mirror-contract")
    p_emit.add_argument("--target", required=True)

    args = parser.parse_args(argv)

    if args.verb == "write":
        return cmd_write(args.target, args.card)
    if args.verb == "verify":
        return cmd_verify(args.target)
    if args.verb == "show":
        return cmd_show(args.target, args.p0_line)
    if args.verb == "emit-mirror-contract":
        return cmd_emit_mirror_contract(args.target)
    return cmd_hash(args.target)


if __name__ == "__main__":
    sys.exit(main())
