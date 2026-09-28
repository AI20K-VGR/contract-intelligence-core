#!/usr/bin/env python3
"""artifact_check.py — artifact presence gate + active-plan resolution.

check_stage(stage, root) returns None (pass) or a BLOCK REASON string — the
core contract run_compliance_hook expects, so the gate hook stays a thin
shell around this module.

Policy is data-driven from harness/data/stage-policy.yaml (override:
HARNESS_STAGE_POLICY env). A missing/malformed policy raises — the compliance
wrapper turns that into exit 2 + guidance (a gate without its policy must not
silently pass).

HONESTY: this is a PRESENCE gate. It proves the step RAN — the
artifact exists, parses, and carries the required fields — it does NOT verify
WHO ran it. Actor fields are attribution, never authorization. The
plan-approval kind is personal-first SLIM: no roster, no quorum, no role rule.
It validates verdict (APPROVED), plan-binding, and a normalized plan-dir hash.
Self-approval is deliberate anti-drift discipline, not an anti-fraud check; it
still does not authenticate anyone — actor strings stay spoofable by design.

Artifacts (machine-written, pure-YAML preferred, legacy JSON read too) live at:
    plans/<active-plan>/artifacts/<kind>.yaml  (or legacy <kind>.json)
Active plan resolution: HARNESS_ACTIVE_PLAN env (path or bare dir name under
plans/) > newest plans/*/plan.md with `status: in_progress` frontmatter.
"""

import json
import os
import sys
from collections import namedtuple
from pathlib import Path


def _yaml_load(text):
    """The one shared YAML read (yaml_io.py, ruamel.yaml, C-accelerated) — see
    that module's docstring for why ruamel replaced PyYAML and hook_runtime.py
    for the parse-cost measurements.

    This module sits on a per-EVENT path, so its parse cost is paid per tool
    call / prompt, not once per CLI run. `import yaml_io` stays lazy and is a
    same-directory sibling import (harness/scripts/), so this file stays
    runnable as a standalone CLI without the hooks dir on sys.path.
    """
    import yaml_io
    return yaml_io.yaml_load(text)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def _ensure_hooks_path():
    """Put the sibling hooks/ dir on sys.path so hook_runtime/trace_log import."""
    hooks = str(Path(__file__).resolve().parent.parent / "hooks")
    if hooks not in sys.path:
        sys.path.append(hooks)


_POLICY_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "stage-policy.yaml"

# Minimal required-fields contract per artifact kind (no jsonschema dep —
# presence + shape only; richer JSON-schemas in harness/schemas/ document the
# full shape for humans and future schema validators).
_REQUIRED_FIELDS = {
    "verification": ("stage", "plan", "actor", "ts", "checks", "verdict"),
    "review-decision": ("verdict", "reviewer", "role", "rationale"),
    "critique-consensus": ("verdict", "reviewer", "role", "rationale", "ts"),
    "security-scan": ("verdict", "stage", "actor", "ts", "findings"),
    "plan-approval": ("schema", "plan", "plan_hash", "author", "reviewer",
                      "verdict", "rationale", "ts"),
    # rule-scan is validated only when PRESENT (never listed in a stage's
    # `requires:` — its presence is an AI-applied boundary the gate won't force).
    "rule-scan": ("rules_applied", "violations", "verdict", "reviewer", "ts"),
    # coverage-grid (the grid-planning primitive's gate artifact) is
    # advisory-only: presence + required-field shape is checked like every
    # other kind above, but there is NO verdict-enforce branch in
    # _check_artifact for it (a `reject` grid never hard-blocks a local
    # stage) — that stays a downstream consumer-wiring decision, not this gate's.
    "coverage-grid": ("gate", "verdict", "agent", "density_tier", "attestation", "ts"),
}

# Cache keyed by policy path: one parse per file per process, and an env
# override pointing elsewhere (tests, odd layouts) naturally misses the cache.
_policy_cache = {}

# When a review artifact is MISSING (no review happened yet), the block reason
# resurfaces the Plannotator review option — the reliable backstop so the
# offer is never silently dropped if the skill forgot to make it at the gate.
# Scoped to the missing case: a present-but-failing artifact is a content
# problem, not a "go review" nudge.
_REVIEW_KINDS = ("plan-approval", "review-decision", "verification")
_PLANNOTATOR_HINT = (
    " — or invite a reviewer via [Review directly (Plannotator) / Approve / "
    "Reject]; see harness/rules/plannotator-review-gates.md"
)


def _policy_path() -> Path:
    raw = os.environ.get("HARNESS_STAGE_POLICY")
    return Path(raw) if raw else _POLICY_DEFAULT


def load_policy() -> dict:
    """Parse stage-policy.yaml once per path per process. Raises LOUD on a
    missing or malformed file — the gate's policy is its spine, never
    default-to-pass."""
    p = _policy_path()
    key = str(p)
    if key in _policy_cache:
        return _policy_cache[key]

    try:
        raw = _yaml_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            "stage policy missing at %s — restore THAT file. Its path comes from "
            "$HARNESS_STAGE_POLICY when that env var is set (e.g. a gitignored "
            ".harness-dev/ dev override), otherwise the shipped "
            "harness/data/stage-policy.yaml. Restoring the shipped default does "
            "not help while the env var points elsewhere." % p
        )
    stages = (raw or {}).get("stages") if isinstance(raw, dict) else None
    if not isinstance(stages, dict) or not stages:
        raise RuntimeError(
            "stage policy %s is malformed — expected a top-level `stages:` mapping" % p
        )
    # NOTE: a hard stage with `require_plan:false` + empty `requires:` is ALLOWED —
    # it does NOT "gate nothing". The always-on checks still run on it: ship/deploy
    # gate on N/N phase completeness (derive_plan_completion), and any stage refuses a
    # present-but-contradictory rule-scan. It is also the deliberate SOLO / personal-
    # first posture (a dev running without formal plans wants a hard stage that skips
    # the plan-presence force but keeps the consistency floor). Local never blocks
    # anyway, so an over-eager schema raise here only broke that legitimate posture — a
    # forgotten `requires:` is caught in review + the remote CI receipts-gate, not by
    # bricking policy load.
    # soft_stage_advisory: top-level on/off for the "[advisory] soft stage X
    # proceeding" reminder a soft stage prints. Default True (the historical
    # behavior). A solo posture sets it false for a fully quiet, no-friction run
    # (the gate still traces every decision — only the stderr nudge is silenced).
    # Anything other than an explicit `false` keeps the reminder on (fail-loud).
    soft_advisory = (raw or {}).get("soft_stage_advisory", True)
    # hard_stage_advisory: the SEPARATE top-level on/off for the "[advisory] hard
    # stage <reason>" line a hard stage prints when a receipt is missing/failed
    # (personal-first: local advises, never blocks). Default True; false = silent
    # (the gate_advisory TRACE is still emitted). Kept independent of
    # soft_stage_advisory so silencing hard noise never loses the soft-stage signal.
    hard_advisory = (raw or {}).get("hard_stage_advisory", True)
    _policy_cache[key] = {
        "stages": stages,
        "soft_stage_advisory": soft_advisory is not False,
        "hard_stage_advisory": hard_advisory is not False,
    }
    return _policy_cache[key]


# status is read ONLY from inside the frontmatter block — a
# `status: in_progress` quoted in the plan body (docs, code examples) must
# never make that plan active. Frontmatter READING itself is delegated to
# `frontmatter_parser` (the one shared owner): a
# local `\A---` regex here used to reject a leading blank line, BOM, or
# leading whitespace that `frontmatter_parser` correctly tolerates, so the
# same disk file could resolve `in_progress` via one reader and "no status"
# via this one — two truths about one plan. Delegating removes the seam.


def _frontmatter_status(text):
    """The plan's raw (unnormalized) frontmatter `status:` value, or None when
    unreadable/absent/malformed. Callers keep doing their own
    `.strip("'\"").replace("-", "_")` normalization — this only reports
    presence + the raw token, exactly like the regex it replaces."""
    import frontmatter_parser

    parsed = frontmatter_parser.parse_text(text)
    if not parsed["ok"]:
        return None
    status = (parsed["frontmatter"] or {}).get("status")
    return str(status) if status is not None else None


def resolve_active_plan(root, allow_completed=False):
    """The active plan dir, or None.

    HARNESS_ACTIVE_PLAN wins: an absolute/relative path, or a bare dir name —
    but it MUST resolve under <root>/plans/ (a dir outside plans/ is rejected so
    a redirected active-plan cannot smuggle forged artifacts past the gate).
    Fallback: newest (by dir name — timestamped) plans/*/plan.md
    whose frontmatter says `status: in_progress`.

    allow_completed opts a caller (only the transport `push` gate, via the
    per-stage allow_completed_plan flag) into a narrow fallback: when NO plan is
    in_progress, anchor to the freshly-closed plan so a close-then-push does not
    read as "no active plan". Guard against a stale weeks-old completed plan
    anchoring an unrelated push: the completed plan is returned ONLY when it is
    the newest plan dir on the board. A newer plan of any status (pending,
    approved, ...) means work moved on — no anchor. Default stays in_progress-
    only, preserving the "only in_progress is active" invariant for every other
    caller (open/close nudges, ship finalize, decision-scope)."""
    root = Path(root)
    raw = os.environ.get("HARNESS_ACTIVE_PLAN")
    if raw:
        cand = Path(raw)
        if not cand.is_absolute():
            under_plans = root / "plans" / raw
            cand = under_plans if under_plans.is_dir() else root / raw
        if not cand.is_dir():
            return None
        # The active plan MUST resolve UNDER <root>/plans/. Otherwise an agent could
        # point HARNESS_ACTIVE_PLAN at a dir it pre-forged PASS artifacts in OUTSIDE
        # the forgery-guarded plans/*/artifacts/ zone, and clear a hard stage with
        # them — the env override is surfaced, but the gate must still fail closed.
        try:
            cand.resolve().relative_to((root / "plans").resolve())
        except ValueError:
            return None
        return cand

    plans = root / "plans"
    if not plans.is_dir():
        return None
    # Newest-first by timestamped dir name. Record each parsed status so the
    # completed-fallback can judge what the most recent plan on the board is.
    dirs = sorted((x for x in plans.iterdir() if x.is_dir()),
                  key=lambda x: x.name, reverse=True)
    actives = []
    statuses = {}  # dir -> normalized status (only dirs with a parseable plan.md)
    for d in dirs:
        pm = d / "plan.md"
        if not pm.is_file():
            continue
        try:
            status = _frontmatter_status(pm.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        norm = status.strip("'\"").replace("-", "_") if status else None
        statuses[d] = norm
        if norm == "in_progress":
            actives.append(d)
    if len(actives) == 1:
        return actives[0]
    if len(actives) > 1:
        # Ambiguous: more than one plan is in_progress (e.g. concurrent
        # sessions) and HARNESS_ACTIVE_PLAN was not set. Refuse to silently bind
        # to an arbitrary one — name the candidates so the operator disambiguates
        # via the env override. A require_plan:true hard stage then blocks (no
        # plan resolved) until it is set; a require_plan:false stage proceeds.
        sys.stderr.write(
            "resolve_active_plan: %d plans are in_progress (%s) and "
            "HARNESS_ACTIVE_PLAN is unset — refusing to guess; set "
            "HARNESS_ACTIVE_PLAN to the intended plan dir\n"
            % (len(actives), ", ".join(p.name for p in actives)))
        return None
    if allow_completed:
        # Zero in_progress. Anchor the freshly-closed plan iff it is the newest
        # plan dir on the board — the first (newest) dir with a parseable status
        # must itself be completed. A newer non-completed plan short-circuits to
        # None so old finished work never clears an unrelated push.
        for d in dirs:
            if d not in statuses:
                continue  # not a plan (no/unreadable plan.md) — cannot shadow
            return d if statuses[d] == "completed" else None
    return None


# Gate artifacts are read in BOTH formats during the SSOT-YAML migration: the
# pure-YAML form (.yaml — the new default a verdict+rationale reads cleanly in)
# is preferred, the legacy .json is the fallback. The forgery seam (gate_stage)
# and write_guard cover BOTH extensions so neither is a write-bypass.
_ARTIFACT_EXTS = (".yaml", ".json")


def _artifact_path(plan_dir: Path, kind: str) -> Path:
    """Resolve the on-disk artifact path for `kind`: the first existing of
    <kind>.yaml then <kind>.json. When neither exists, return the .yaml path
    (the canonical default) so a 'missing' message points at the right form."""
    base = plan_dir / "artifacts"
    for ext in _ARTIFACT_EXTS:
        cand = base / ("%s%s" % (kind, ext))
        if cand.is_file():
            return cand
    return base / ("%s.yaml" % kind)


def _parse_artifact_text(text: str, path: Path):
    """(record, error). Dispatch by extension. A .yaml artifact is parsed with
    yaml_io.yaml_load, catching yaml_io.YAMLError SEPARATELY — it is NOT a
    subclass of ValueError/OSError, so a multi-doc or malformed YAML would
    otherwise crash the gate (self-DoS) instead of failing closed with a
    message."""
    if path.suffix == ".yaml":
        import yaml_io
        try:
            return _yaml_load(text), None
        except (yaml_io.YAMLError, ValueError) as e:
            # ruamel's timestamp/int constructors can raise a bare ValueError
            # too; treat both as a parse failure → fail closed with a message,
            # never crash.
            return None, "unreadable YAML (%s)" % e
    try:
        return json.loads(text), None
    except ValueError as e:
        return None, "unreadable (%s)" % e


def _load_artifact(plan_dir: Path, kind: str):
    """(record, problem). Missing file → (None, 'missing'); bad parse/shape →
    (None, description); ok → (dict, None). Reads .yaml (preferred) or .json."""
    p = _artifact_path(plan_dir, kind)
    # Containment: the artifact must resolve to a REAL path under the plan dir. A
    # forged PASS planted outside the forgery-guarded zone + `ln -s ../../evil
    # plans/<p>/artifacts` would otherwise be read through the symlink and clear a
    # hard stage (the plan-DIR check one level up does not inspect this child).
    try:
        p.resolve(strict=False).relative_to(plan_dir.resolve())
    except ValueError:
        return None, "resolves outside the plan's artifacts/ dir (symlink escape — forged)"
    if not p.is_file():
        return None, "missing"
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, "unreadable (%s)" % e
    rec, err = _parse_artifact_text(text, p)
    if err:
        return None, err
    if not isinstance(rec, dict):
        return None, "not a %s object" % ("YAML" if p.suffix == ".yaml" else "JSON")
    return rec, None


def failing_checks_reason(rec):
    """None when every check in a verification record is green, else why not.

    PASS-allowlist, not a FAIL-denylist: per-check status is a closed enum
    {PASS,FAIL,SKIP} (schema), so anything else fails CLOSED — a crashed verifier
    writing ERROR/TIMEOUT, a missing status, a typo, a non-dict entry, or one of
    the off-schema statuses in live use (BLOCKED, UNMEASURED, UNOWNED, UNPROVABLE,
    …) which all mean "not measured green". Fail-open here would let a broken
    verifier clear a hard stage.

    Public because the gate is not the only reader: derive_plan_completion counts
    a phase done by the SAME rule. They used to disagree — the counter read only
    `verdict`, so a phase carrying PASS_WITH_RISK over red checks was simultaneously
    "done" to the counter and blocked at the gate. One function, two callers; a
    hand-copied second implementation is what produced that divergence.
    """
    checks = rec.get("checks")
    if not isinstance(checks, list) or not checks:
        return ("artifact 'verification' has no checks — at least one "
                "named check is required")
    bad = [c.get("name", "?") if isinstance(c, dict) else "?"
           for c in checks
           if not isinstance(c, dict) or c.get("status") not in ("PASS", "SKIP")]
    if bad:
        return ("verification has non-passing check(s): %s — every check must "
                "be PASS or SKIP (a FAILed, ERRORed, or missing status fails "
                "closed). Fix and re-run before this stage" % ", ".join(bad))
    return None


def _phase_snapshot_sweep(plan_dir: Path):
    """None when every per-phase snapshot is green, else why not — and how many
    were read, so the caller can say what it looked at.

    The canonical verification.json is by design the CURRENT phase's verdict:
    verification_snapshot.py overwrites it on every phase write. Earlier phases
    survive only as verification-<phase>.json. Nothing read those, so a plan
    could clear a hard stage on one green phase while every earlier phase was
    still red — a gate that reports "clean" over a span it never looked at.

    Phase ids are free-form (verification_snapshot._SAFE_PHASE_RE allows
    [A-Za-z0-9_-]+) and carry no order: "3a", "4g" and "3-1" are all legal ids,
    and phase 3 may finish before phase 2. So this sweeps the SET of files that
    exist and assumes nothing about their names or sequence.

    Absence is not a finding: a plan that never ran a phased cook has no
    snapshots, and that is the pass it always was. A snapshot that exists but
    cannot be read IS a finding — fails closed, like every other unreadable
    artifact on this path.
    """
    art = plan_dir / "artifacts"
    if not art.is_dir():
        return None, 0
    problems = []
    n = 0
    seen = set()
    for f in sorted(art.glob("verification-*.json")):
        phase = f.name[len("verification-"):-len(".json")]
        n += 1
        seen.add(phase)
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append("%s is unreadable (%s)" % (phase, exc.__class__.__name__))
            continue
        if not isinstance(rec, dict):
            problems.append("%s is not a verification record" % phase)
            continue
        verdict = rec.get("verdict")
        if verdict not in ("PASS", "PASS_WITH_RISK"):
            problems.append("%s carries verdict %r" % (phase, verdict))
            continue
        red = failing_checks_reason(rec)
        if red:
            problems.append("%s: %s" % (phase, red))
    # The file sweep is blind to a phase that wrote NOTHING — no file, no finding.
    # The plan-graph names the phases that were meant to exist, so a declared node
    # with no snapshot is a gap rather than a pass. An absent/unparseable sidecar
    # leaves the file sweep exactly as it was: judge what is on disk, never invent
    # a denominator.
    #
    # Gated on n: a plan may carry a plan-graph and still verify ONCE at the end
    # rather than per phase, which is the un-phased path — zero snapshots there
    # means "this plan does not work that way", not "every phase is missing". Only
    # once a phased cook has written at least one snapshot does the graph become a
    # denominator to hold the rest against.
    declared: tuple = ()
    if n:
        try:
            _scripts = os.path.dirname(os.path.abspath(__file__))
            if _scripts not in sys.path:
                sys.path.insert(0, _scripts)
            import plan_graph  # type: ignore[import-not-found]  # sibling in scripts/
            graph = plan_graph.parse_phase_graph(plan_dir)
            if "error" not in graph:
                # A paused phase is not going to write a snapshot — that is what the
                # pause MEANS — so demanding one blocks the plan on work its author
                # deliberately deferred. Note the asymmetry: this only excuses a
                # phase that wrote NOTHING. A paused phase whose snapshot exists and
                # is red is still read below, because pausing must not become an
                # erase button for a verdict the author dislikes.
                declared = tuple(plan_graph._all_nodes(graph)
                                 - plan_graph.paused_phases(graph))
        except Exception:  # noqa: BLE001 — no sidecar read is worth bricking a gate
            declared = ()
    missing = [p for p in declared if p not in seen]
    if missing:
        problems.append("declared in plan-graph but no verification snapshot: %s"
                        % ", ".join(sorted(missing)))

    if problems:
        return ("earlier phase(s) have not passed (read %d phase snapshot(s)%s) — "
                "%s. The gate reads every verification-<phase>.json, not only the "
                "current phase's verification.json"
                % (n,
                   ", %d declared in plan-graph" % len(declared) if declared else "",
                   "; ".join(problems))), n
    return None, n


def _check_artifact(plan_dir: Path, kind: str, root=None, stage=None):
    """None when the artifact satisfies the presence + verdict policy, else
    an actionable reason naming the artifact, the field, and the fix path."""
    if kind not in _REQUIRED_FIELDS:
        # An unrecognized requires-kind (a stage-policy typo, or a kind added to
        # policy before the code) must fail LOUD — never downgrade a hard stage to
        # "any present JSON object passes".
        return ("stage requires unknown artifact kind %r — not a recognized gate "
                "artifact; fix the requires: list in harness/data/stage-policy.yaml"
                % kind)
    where = plan_dir / "artifacts"
    rec, problem = _load_artifact(plan_dir, kind)
    if rec is None:
        hint = _PLANNOTATOR_HINT if kind in _REVIEW_KINDS else ""
        if kind == "plan-approval":
            return (
                "artifact 'plan-approval' %s — a rostered reviewer writes it "
                "via: python3 harness/scripts/plan_approval.py --plan %s "
                "--verdict APPROVED --rationale '...' (the CLI enforces the "
                "role rule before writing)%s" % (problem, plan_dir, hint)
            )
        if kind == "critique-consensus":
            return (
                "artifact 'critique-consensus' %s — run the critique in GATE mode "
                "to produce it: /hs:critique --gate (writes %s/critique-consensus"
                ".yaml with the consolidated machine verdict; a hard stage passes "
                "only on verdict PASS). Plain /hs:critique is advisory and writes "
                "no gate artifact." % (problem, where)
            )
        return (
            "artifact %r %s — create %s/%s.yaml (see harness/schemas/)%s"
            % (kind, problem, where, kind, hint)
        )
    missing = [f for f in _REQUIRED_FIELDS.get(kind, ()) if f not in rec]
    if missing:
        return (
            "artifact %r at %s/%s is missing required field(s): %s"
            % (kind, where, _artifact_path(plan_dir, kind).name, ", ".join(missing))
        )
    if kind == "verification":
        # Bind the artifact to THIS plan: a verification.json physically copied
        # from another plan's artifacts dir (same shape, a real PASS) must not
        # clear this plan's gate. The writer records plan_dir.name, so a name
        # mismatch is a cross-plan replay.
        if rec.get("plan") != plan_dir.name:
            return ("verification artifact names plan %r but the active plan is "
                    "%r — an artifact produced for another plan cannot clear this "
                    "stage; re-run verification for this plan"
                    % (rec.get("plan"), plan_dir.name))
        checks_problem = failing_checks_reason(rec)
        if checks_problem:
            return checks_problem
        # The verifier's overall verdict is an ALLOWLIST, not a BLOCKED-only
        # denylist: verdict is a required field, so a crashed verifier writing
        # ERROR/TIMEOUT/"" — or any off-enum value — must fail CLOSED, not slip
        # through merely because it is not the literal "BLOCKED" (the suite may
        # have SKIPped every check, so the per-check gate alone cannot catch it).
        verdict = rec.get("verdict")
        if verdict not in ("PASS", "PASS_WITH_RISK"):
            return ("verification verdict is %r — a hard stage needs PASS or "
                    "PASS_WITH_RISK; anything else (a crashed-verifier "
                    "ERROR/TIMEOUT, an empty or off-enum value) fails CLOSED. "
                    "Resolve and re-run verification" % verdict)
    # review-decision + critique-consensus share one rule: a hard stage needs
    # exactly PASS; only the parenthetical reason differs.
    _pass_only = {
        "review-decision": "PASS_WITH_RISK is a conscious soft-accept, not a "
                           "ship license; BLOCKED means stop",
        "critique-consensus": "PASS_WITH_RISK is a conscious soft-accept; "
                              "BLOCKED means stop",
    }
    if kind in _pass_only and rec.get("verdict") != "PASS":
        return ("%s verdict is %r but a hard stage needs exactly PASS (%s)"
                % (kind, rec.get("verdict"), _pass_only[kind]))
    if kind == "security-scan":
        verdict = rec.get("verdict")
        if verdict != "PASS":
            return (
                "security-scan verdict is %r but a stage that opted into the "
                "security-scan gate needs exactly PASS — resolve the HIGH/CRITICAL "
                "findings (or accept them by re-running the scan to a PASS verdict) "
                "before this stage. This gate ships OFF: it only fires when a stage "
                "lists `security-scan` in its stage-policy `requires:`." % verdict
            )
        # PASS must be CONSISTENT with the findings (like verification inspects its
        # checks, not just the top verdict): a still-OPEN high/critical cannot ride
        # a self-declared PASS — that would be a name-vs-enforcement gap.
        findings = rec.get("findings")
        if findings is not None and not isinstance(findings, list):
            return (
                "security-scan 'findings' must be a list (got %s) — a malformed "
                "findings shape cannot be consistency-checked against a PASS verdict."
                % type(findings).__name__
            )
        open_sev = [f for f in (findings or [])
                    if isinstance(f, dict)
                    and str(f.get("severity", "")).lower() in ("critical", "high")
                    and str(f.get("status", "open")).lower() not in ("accepted", "fixed")]
        if open_sev:
            return (
                "security-scan verdict is PASS but %d HIGH/CRITICAL finding(s) are "
                "still open — mark them fixed/accepted or the PASS is not honest "
                "(severity+status are in the artifact's findings list)" % len(open_sev)
            )
    if kind == "plan-approval":
        return _check_plan_approval(plan_dir, rec, root, stage)
    return None

def _check_plan_approval(plan_dir: Path, rec: dict, root, stage=None):
    """Plan-binding + anti-drift validation for a self-approved plan.

    Personal-first SLIM: no roster, no quorum, no role layer — self-approval is
    deliberate discipline, not an anti-fraud check. The one present record is
    validated for verdict (APPROVED), plan binding, and plan_hash drift. `stage`
    is accepted for caller compatibility but no longer selects a quorum policy.
    Local file reads only — the gate path stays network-free."""
    import plan_approval as pa

    if rec.get("verdict") != "APPROVED":
        return (
            "plan-approval verdict is %r — the plan must be APPROVED before this "
            "stage (re-run plan_approval.py after the concerns are addressed)"
            % rec.get("verdict")
        )

    # Bind the approval to THIS plan: an APPROVED artifact for another plan must
    # not clear this stage even when the plan bodies hash alike (identical
    # content -> identical plan_hash). The writer records plan_dir.name.
    if rec.get("plan") != plan_dir.name:
        return ("plan-approval artifact names plan %r but the active plan is %r "
                "— an approval for another plan cannot clear this stage; re-run "
                "plan_approval.py for this plan"
                % (rec.get("plan"), plan_dir.name))

    current = pa.plan_hash(plan_dir)
    if rec.get("plan_hash") != current:
        recorded = rec.get("file_hashes") or {}
        now = pa.file_hashes(plan_dir)
        drifted = sorted(
            set(k for k in now if now.get(k) != recorded.get(k))
            | set(k for k in recorded if k not in now))
        return (
            "plan content changed after approval (drifted: %s) — the plan "
            "body must be re-approved: re-run plan_approval.py. Frontmatter "
            "status and the plan.md Phases table are exempt; any body edit "
            "re-opens approval — that friction is the anti-drift working, not a bug"
            % (", ".join(drifted) or "unknown — re-run plan_approval.py")
        )
    return None


# Append-only trace helper for the rule-coverage ramp (soft warn / internal error).
# Named _trace_override for historical reasons — the break-glass override feature it
# once served was removed under personal-first; this now only records coverage traces.
def _trace_override(plan_dir: Path, stage: str, kind: str, rec: dict) -> None:
    """Record a rule-coverage trace event (append-only, fail-open)."""
    try:
        _ensure_hooks_path()
        import trace_log
        import hook_runtime
        trace_log.append_event(
            "artifact_check", "gate_override",
            actor=rec.get("actor") or hook_runtime.resolve_actor(),
            target=plan_dir.name, status=stage,
            note="kind=%s reason=%s" % (kind, rec.get("reason")))
    except Exception:  # noqa: BLE001 — tracing never blocks the gate
        pass


# --- DoD-by-change-class evaluation (folded into ONE compliance hook) ---
# gate_stage calls evaluate_test_policy AFTER the presence check clears, then
# routes its FAIL reason through guard_policy.gate("test_policy_dod", ...). No
# second compliance hook is added (no double-block, no order ambiguity).
#
# HONESTY: this re-reads the RAW normalized result files (test_result_readers),
# NOT the artifact's self-declared check.status/verdict — self-report does not
# self-approve. It proves the result FILES say pass; it cannot prove real tests
# ran (presence gate, not authentication — same posture as the rest of the gate).
TestPolicyVerdict = namedtuple("TestPolicyVerdict",
                               ["status", "reason", "enforcement"])

_READER_FOR = {"junit": "read_junit", "cobertura": "read_cobertura",
               "jacoco": "read_jacoco", "sarif": "read_sarif"}


def _resolve_now(root=None) -> str:
    """Current date as YYYY-MM-DD for grace-expiry comparison. INJECTED, never a
    bare wall-clock read in the gate: HARNESS_NOW env > the repo HEAD commit date
    (deterministic, git-visible) > date.today() as the last resort. ISO dates
    string-compare correctly, so this stays a plain string."""
    env = os.environ.get("HARNESS_NOW")
    if env and env.strip():
        return env.strip()[:10]
    try:
        import subprocess
        r = root or os.getcwd()
        out = subprocess.run(["git", "-C", str(r), "log", "-1", "--format=%cI"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()[:10]
    except Exception:  # noqa: BLE001 — git absent → fall through
        pass
    from datetime import date
    return date.today().isoformat()


def _apply_grace_expiry(spec, change_class, root):
    """If `spec` carries an expired grace, restore the pre-grace (full hard)
    gate from grace.restores and emit a grace_expired trace. Returns (spec,
    graced): graced is False once a grace is expired (the door has closed)."""
    grace = spec.get("grace")
    if not (isinstance(grace, dict) and grace.get("expires")):
        return spec, bool(grace)
    now = _resolve_now(root)
    # Coerce to the ISO date string before comparison: a quoted expires is
    # already a string, but an unquoted one (parsed to datetime.date) would make
    # `date >= str` crash. load_test_policy rejects the unquoted form loudly; this
    # is the belt for any path that injects a non-string after load.
    expires = str(grace["expires"])[:10]
    if expires >= now:
        return spec, True  # still in grace
    restores = grace.get("restores") or {}
    restored = dict(spec)
    restored["required"] = restores.get("required", spec.get("required"))
    restored["enforcement"] = restores.get("enforcement", "hard")
    restored["coverage"] = restores.get("coverage", spec.get("coverage"))
    restored.pop("grace", None)
    try:
        _ensure_hooks_path()
        import trace_log
        trace_log.append_event("artifact_check", "grace_expired",
                               target=change_class,
                               note="expired %s (now %s) — full hard gate restored"
                               % (grace.get("expires"), now))
    except Exception:  # noqa: BLE001 — tracing never blocks the gate
        pass
    return restored, False

# enforcement strictness rank — strictest among failed requirements decides
# whether the gate blocks (hard) or merely advises (soft).
_ENFORCE_RANK = {"hard": 2, "soft": 1, "advisory": 0, "off": 0}


def _matching_components(policy: dict, changed_paths):
    """Components whose `path` glob matches at least one changed path. fnmatch
    with a leading-** convenience: `**/auth/**` also matches a top-level
    `auth/x` (fnmatch does not treat ** specially, so we also test the pattern
    with a leading `**/` stripped). A component with no changed-path match
    contributes nothing — a non-sensitive change is never security-gated."""
    import path_glob
    paths = [str(p) for p in (changed_paths or [])]
    out = []
    for comp in (policy.get("components") or []):
        if not isinstance(comp, dict):
            continue
        pat = comp.get("path")
        if not pat:
            continue
        if path_glob.match_any_path(paths, pat):
            out.append(comp)
    return out


def _read_normalized_result(plan_dir: Path, rel_file: str, fmt: str):
    """(data, problem). Symlink-escape-safe like _load_artifact: the result file
    MUST resolve under plans/<p>/artifacts/. A missing/over-cap/malformed file is
    a clear problem string, never a crash."""
    art = plan_dir / "artifacts"
    p = art / rel_file
    try:
        p.resolve(strict=False).relative_to(art.resolve())
    except ValueError:
        return None, "result path escapes the artifacts/ dir (forged)"
    if not p.is_file():
        return None, "result file %s is missing" % rel_file
    reader_name = _READER_FOR.get(fmt)
    if reader_name is None:
        return None, "unknown result format %r" % fmt
    try:
        import test_result_readers as rdr
    except ImportError as e:
        return None, "result reader unavailable: %s" % e
    try:
        return getattr(rdr, reader_name)(p), None
    except Exception as e:  # noqa: BLE001 — reader raises TestResultError; one clear problem
        return None, "result %s unreadable: %s" % (rel_file, e)


def validate_verification_wellformed(plan_dir, root=None):
    """(ok, problems): STRUCTURAL well-formedness of the verification artifact.

    A shift-left producer check — deliberately narrower than evaluate_test_policy.
    For every check that declares a `format` other than "manual", it asserts:
      - `name` is a canonical test_type (a key in test-policy's `test_types`), so
        the DoD gate's by_name lookup will find it (catches `jest-unit` early); and
      - `file` is present and parses with that format's reader.
    Status-only checks (no `format`) and `manual` checks travel other evidence
    paths and are out of scope. This judges STRUCTURE, never policy — an empty-
    but-valid result file is well-formed (the DoD floor is the gate's job, not
    this validator's). Independent of git diff: it inspects every format-bearing
    check, not the change-class's required set.
    """
    plan_dir = Path(plan_dir)
    rec, problem = _load_artifact(plan_dir, "verification")
    if rec is None:
        return False, ["verification artifact is unreadable: %s" % problem]
    checks = rec.get("checks")
    if not isinstance(checks, list):
        return False, ["verification artifact has no `checks` list to validate"]
    try:
        import test_policy
        test_types = test_policy.load_test_policy(root=root).get("test_types") or {}
    except Exception as e:  # noqa: BLE001 — no policy → names cannot be validated
        return False, ["test-policy could not be loaded to validate names: %s" % e]
    # NOTE: a False return here can be either a config emergency (policy unreadable)
    # or a real validation failure (bad check names). Callers that need to distinguish
    # should inspect the problem text for "could not be loaded" vs "check" phrasing.
    canonical = ", ".join(sorted(test_types))
    problems = []
    for c in checks:
        if not isinstance(c, dict):
            continue
        fmt = c.get("format")
        if not fmt or fmt == "manual":
            continue  # status-only / manual checks are out of well-formedness scope
        name = c.get("name")
        if not name:
            problems.append(
                "a check declares format %r but no `name` — a DoD-bearing check "
                "needs a canonical test_type name (one of: %s)" % (fmt, canonical))
        elif name not in test_types:
            problems.append(
                "check %r carries format %r but %r is not a canonical test_type "
                "(use one of: %s)" % (name, fmt, name, canonical))
        rel = c.get("file")
        if not rel:
            problems.append(
                "check %r (format %r) declares a format but no result `file` to "
                "verify (add `file:` on the check)" % (name, fmt))
            continue
        _data, fproblem = _read_normalized_result(plan_dir, rel, fmt)
        if fproblem:
            problems.append(
                "check %r (format %r) has no parseable result file: %s"
                % (name, fmt, fproblem))
    return (len(problems) == 0), problems


def _coverage_threshold(spec: dict):
    """The numeric line-coverage floor for this class, or None when unset /
    `no_regression` (the relative band is a P3 telemetry concern, not a hard
    numeric gate here)."""
    line = (spec.get("coverage") or {}).get("line")
    return line if isinstance(line, (int, float)) else None


def evaluate_test_policy(plan_dir, change_class, changed_paths, root=None,
                         ambiguous=False):
    """Return a TestPolicyVerdict for a change-class against its DoD.

    Resolves the required test types + enforcement from test-policy, then
    RE-DERIVES pass/fail from the raw result files referenced in
    verification.json's checks (name -> {format, file}). A missing required
    type, a failing raw result, or coverage below the numeric threshold ->
    status FAIL. enforcement (soft when the class is soft or `ambiguous`) rides
    along so the caller routes soft -> advisory. A graced class reports GRACE
    on an otherwise-clean run. A broken policy fails CLOSED (hard FAIL)."""
    plan_dir = Path(plan_dir)
    try:
        import test_policy
        policy = test_policy.load_test_policy(root=root)
    except Exception as e:  # noqa: BLE001 — a gate with no policy fails closed
        return TestPolicyVerdict("FAIL", "test-policy could not be loaded: %s — "
                                 "fix harness/data/test-policy.yaml" % e, "hard")

    try:
        spec = test_policy.resolve_for_class(policy, change_class)
        spec, graced = _apply_grace_expiry(spec, change_class, root)
    except test_policy.TestPolicyError as e:
        return TestPolicyVerdict("FAIL", str(e), "hard")
    except Exception as e:  # noqa: BLE001 — a resolve/grace crash blocks LOUD, not silently
        return TestPolicyVerdict(
            "FAIL", "grace.expires must be a quoted ISO date string — resolving "
            "the DoD crashed (%s); quote it in test-policy.yaml" % e, "hard")
    class_enf = "soft" if ambiguous else spec.get("enforcement", "hard")
    cov_floor = _coverage_threshold(spec)
    test_types_cfg = policy.get("test_types") or {}

    # Required types come from the class (at the class enforcement) PLUS any
    # component whose glob matches a changed path (at the component enforcement —
    # a security overlay can demand HARD even on a soft class). Strictest
    # enforcement wins per type, so a component never lowers a class requirement.
    requirements = {}  # test_type -> enforcement

    def _want(tt, enf):
        if _ENFORCE_RANK.get(enf, 0) >= _ENFORCE_RANK.get(requirements.get(tt), -1):
            requirements[tt] = enf

    for tt in (spec.get("required") or []):
        _want(tt, class_enf)
    for comp in _matching_components(policy, changed_paths):
        comp_enf = comp.get("enforcement") or class_enf
        for tt in (comp.get("required") or []):
            _want(tt, comp_enf)
    if cov_floor is not None:
        _want("coverage", class_enf)  # numeric floor → coverage is required

    rec, _problem = _load_artifact(plan_dir, "verification")
    by_name = {}
    if isinstance(rec, dict):
        for c in rec.get("checks") or []:
            if isinstance(c, dict) and c.get("name"):
                by_name[c["name"]] = c

    failures = []  # (detail, enforcement)

    def _detail(tt, enf):
        """A failure string for required type tt at enforcement enf, or None
        when it passes."""
        c = by_name.get(tt)
        if not c:
            return ("missing required test type %r (no check in "
                    "the verification artifact)" % tt)
        tt_cfg = test_types_cfg.get(tt)
        fmt = c.get("format") or (tt_cfg.get("format") if isinstance(tt_cfg, dict) else None)
        if fmt == "manual":
            # A manual-test check carries evidence_tier + an anchor citation, not
            # a result file. Hard requirement → needs anchored output AND a human
            # charter co-sign; soft → only a fabricated (rejected) anchor fails.
            import manual_test
            import harness_paths
            state = harness_paths.state_dir()
            if enf == "hard":
                team_root = Path(root) if root else harness_paths.root()
                team_path = team_root / "harness" / "data" / "team.yaml"
                ok, why = manual_test.hard_admissible(c, state, team_path=team_path)
                return None if ok else "required manual type %r: %s" % (tt, why)
            tier, why = manual_test.admissibility(c, state)
            return ("required manual type %r: %s" % (tt, why)
                    if tier == "rejected" else None)
        rel = c.get("file")
        if not fmt or not rel:
            return ("required type %r carries no raw result file to verify "
                    "(need format + file on the check)" % tt)
        data, problem = _read_normalized_result(plan_dir, rel, fmt)
        if problem:
            return "required type %r %s" % (tt, problem)
        if fmt == "junit":
            bad = (data.get("failed", 0) or 0) + (data.get("errors", 0) or 0)
            if bad > 0:
                return ("required type %r has failing tests (%d failed, %d "
                        "errors)" % (tt, data.get("failed", 0),
                                     data.get("errors", 0)))
        elif fmt in ("cobertura", "jacoco"):
            if cov_floor is not None and (data.get("line_rate") or 0) * 100 < cov_floor:
                return ("coverage %.0f%% is below the required %s%% line floor"
                        % ((data.get("line_rate") or 0) * 100, cov_floor))
        elif fmt == "sarif":
            import test_result_readers as rdr
            verdict, sdetail = rdr.sarif_verdict(data)
            if verdict == "FAIL":
                return "required type %r has %s" % (tt, sdetail)
        return None

    for tt, enf in requirements.items():
        d = _detail(tt, enf)
        if d:
            failures.append((d, enf))

    if not failures:
        return TestPolicyVerdict("GRACE" if graced else "PASS", None, class_enf)
    # The gate blocks when ANY failed requirement is hard; otherwise advisory.
    overall = max((enf for _d, enf in failures),
                  key=lambda e: _ENFORCE_RANK.get(e, 0))
    reason = ("test DoD for change-class %r not met: %s"
              % (change_class, "; ".join(d for d, _e in failures)))
    return TestPolicyVerdict("FAIL", reason, overall)


def _coverage_mode() -> str:
    """The rule-coverage ramp: off | soft | hard. Default SOFT for all of 2.2
    (warn, never block) — hard is deferred until the recorded-changed_files
    derivation is proven on real diffs. Env HARNESS_RULE_COVERAGE overrides."""
    raw = (os.environ.get("HARNESS_RULE_COVERAGE") or "").strip().lower()
    return raw if raw in ("off", "soft", "hard") else "soft"

def _coverage_check(plan_dir: Path, rec: dict):
    """Refuse a rule-scan that omits an applicable operational rule.

    The applicable set is derived from scope cap the diff the producer RECORDED
    (rec['changed_files'] — never a fresh git diff, which would check a
    different file universe than was reviewed). A rule may be cleared by a
    capability-gated skip, EXCEPT a floor rule, which is never skippable.
    Ramp: off -> no-op; soft -> trace a warning, exit clean; hard -> block. No
    recorded changed_files -> no-op (presence-only). Fail-closed: an
    internal error blocks with an actionable reason.

    Asymmetry note: the diff side is producer-pinned (rec['changed_files']), but
    the applicable RULE set is gate-derived here (tree resolution + the live
    standards.user.yaml at gate-time), not pinned by the producer. So the rule
    universe can drift if the tree or user.yaml changes between review and gate.
    This is harmless under the shipped default (soft = warn-only, internal errors
    never block); it becomes load-bearing only when hard mode is enabled, which
    is deferred pending real-diff proof."""
    mode = _coverage_mode()
    if mode == "off":
        return None
    try:
        cf = rec.get("changed_files")
        if not isinstance(cf, list) or not cf:
            return None  # no recorded diff -> no-op (never re-derive git)
        import harness_paths
        import rule_view
        root = harness_paths.root()
        loaded = rule_view.load_rules_from_tree(root, cf)
        applicable = {r.get("id"): r for r in loaded["rules"] if r.get("id")}
        applied = set(rec.get("rules_applied") or [])
        # Personal-first: the capability-gated skip layer is gone (no override_gate
        # role), so a missing applicable rule is simply missing.
        missing = set(applicable) - applied
        if not missing:
            return None
        if mode == "soft":
            _trace_override(plan_dir, "rule-coverage-warn",
                            ",".join(sorted(missing)),
                            {"actor": "system", "reason": "soft ramp — advisory only"})
            return None
        return (
            "rule-coverage: rule-scan omits applicable operational rule(s): %s "
            "(derived from rule-scan.changed_files). Add them to rules_applied "
            "or turn the coverage ramp off."
            % ", ".join(sorted(missing)))
    except Exception as exc:  # noqa: BLE001 — honor the ramp on an internal error
        # soft must never block (advisory ramp); only hard fails closed to a block.
        if mode != "hard":
            _trace_override(plan_dir, "rule-coverage-error", "internal",
                            {"actor": "system", "reason": str(exc)})
            return None
        return "rule-coverage check failed (fail-closed): %s" % exc


# ---------------------------------------------------------------------------
# Stage-floor: per-stage effort/rounds self-discipline check (opt-in, OFF by
# default). This is NOT a real gate boundary — a malformed or absent policy
# MUST be a no-op (fail-soft), never bricking a ship gate over a knob typo.
# ---------------------------------------------------------------------------

# Rank for effort comparison: higher index = stricter effort.
# Defined locally so the gate stays self-contained (no import of a skill helper).
_EFFORT_RANK = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}

# Env override for the review-policy path (tests inject this; production reads
# the shipped harness/data/review-policy.yaml via review_policy_config's default).
_REVIEW_POLICY_ENV = "HARNESS_REVIEW_POLICY"


def _check_stage_floor(plan_dir: Path, stage: str, root=None):
    """Optional effort/rounds floor for a hard stage.

    HONESTY: This floor is SELF-REPORT, easily forged (forgery-gate). It is a
    presence-gate, NOT authentication. A reviewer can write any effort/rounds
    value. Real assurance comes from verdict=PASS + code_evidence, not from
    this floor. The floor is a self-discipline tier — it reminds a team to use
    the right review depth, not a cryptographic guarantee.

    Fail-soft boundary, NARROWED (this is the one place it is NOT absolute):
    when the cheap peek below cannot even tell whether the floor is on (an
    absent file, unreadable/malformed top-level YAML, or a non-mapping
    document) — return None (NO-OP) + emit a loud trace. A typo in an
    advisory knob file the peek cannot even parse must never brick a ship
    gate on a guess.

    But once the peek DOES cleanly read `stage_floor[stage].enabled: true` —
    proof the operator deliberately turned this floor on — a SUBSEQUENT
    failure to load/validate the stage_floor block for real (e.g. a
    misspelled `min_efort`) is no longer an ambiguous "can't tell" case: it is
    a floor that was switched ON now silently going dark. That state must be
    VISIBLE, so this blocks instead of no-op'ing (see review_policy_config.py's
    `load_stage_floor` for why a typo in the unrelated `profiles` block is
    walled off from this and can never trip it).

    Cost note: this function is reachable from gate_stage.py, a PreToolUse
    hook — a fresh process per matching Bash call. The floor ships OFF for
    every stage, so step 0 below is a cheap ruamel-only peek
    (review_policy_config.stage_floor_peek) that short-circuits BEFORE the
    typed `load_stage_floor` call, which imports omegaconf for its deep
    merge (152 modules, ~65 ms — affordable only for the rare, opted-in case,
    never the default path). See review_policy_config.py's module docstring.
    """
    policy_path = os.environ.get(_REVIEW_POLICY_ENV)

    # -- 0. Cheap peek: is this stage's floor even on? -----------------------
    # Wrapped the same as the full load below — `review_policy_config` itself
    # failing to import must still be a no-op, not a brick.
    try:
        _rpc_scripts = os.path.dirname(os.path.abspath(__file__))
        if _rpc_scripts not in sys.path:
            sys.path.insert(0, _rpc_scripts)
        import review_policy_config as _rpc
        enabled, peek_err = _rpc.stage_floor_peek(
            stage, path=policy_path if policy_path else None)
    except Exception as exc:  # noqa: BLE001 — any error -> no-op, never block
        try:
            _ensure_hooks_path()
            import trace_log
            trace_log.append_event(
                "artifact_check", "stage_floor_unevaluated",
                actor="system", target=str(plan_dir),
                note="stage=%s review-policy peek failed (fail-soft): %s"
                     % (stage, exc))
        except Exception:  # noqa: BLE001 — tracing never blocks
            pass
        return None

    if enabled is None and peek_err is not None:
        # A floor block for this stage exists and its `enabled` value cannot be read.
        # Somebody opted in; the opt-in is broken. Blocking is the honest answer — the
        # alternative silently switches off a gate a team deliberately turned on.
        return ("stage floor for %r is configured but its enabled flag is unreadable "
                "(%s) — fix the value (write `true` or `false`) before this stage"
                % (stage, peek_err))

    if peek_err is not None:
        # The peek itself could not determine enabled/disabled (unreadable or
        # malformed top-level document) — genuinely ambiguous, so this stays
        # fail-soft. Traced (restoring the visibility a swallow-everything
        # peek used to cost: before, this same malformed-policy case reached
        # the loader below and traced there; folding the peek in front of it
        # must not silently drop that one event).
        try:
            _ensure_hooks_path()
            import trace_log
            trace_log.append_event(
                "artifact_check", "stage_floor_unevaluated",
                actor="system", target=str(plan_dir),
                note="stage=%s review-policy peek could not determine "
                     "enabled state (fail-soft): %s" % (stage, peek_err))
        except Exception:  # noqa: BLE001 — tracing never blocks
            pass
        return None

    if not enabled:
        return None  # cleanly off — the common case, silent, no trace noise

    # -- 1. Floor is confirmed ON — load ONLY the stage_floor block for real -
    # (never load_review_policy: that also parses `profiles`, and a typo there
    # must not be able to take this floor down — see load_stage_floor's docstring)
    try:
        # `stage=` narrows validation to this stage: a typo under a DIFFERENT stage
        # must not fail-closed the one being checked.
        floor_cfg = _rpc.load_stage_floor(
            path=policy_path if policy_path else None, stage=stage).get(stage)
    except Exception as exc:  # noqa: BLE001 — surfaced as a BLOCK, not swallowed
        try:
            _ensure_hooks_path()
            import trace_log
            trace_log.append_event(
                "artifact_check", "stage_floor_load_failed",
                actor="system", target=str(plan_dir),
                note="stage=%s floor was ON but stage_floor block failed to "
                     "load: %s" % (stage, exc))
        except Exception:  # noqa: BLE001 — tracing never blocks
            pass
        return (
            "stage floor is ON for %r but review-policy.yaml's stage_floor "
            "block could not be parsed (%s) — the floor was explicitly "
            "enabled, so a broken policy fails closed instead of silently "
            "no-op'ing; fix the typo (or set stage_floor.%s.enabled: false to "
            "turn the floor off) before this stage" % (stage, exc, stage)
        )

    if not isinstance(floor_cfg, dict) or not floor_cfg.get("enabled"):
        # The isolated stage_floor loader disagrees with the peek (e.g. a
        # schema-driven default filled `enabled` differently) — treat as off,
        # matching the peek's own read; nothing to check.
        return None

    # -- 2. Floor is enabled: load review-decision and check effort/rounds ---
    min_effort = floor_cfg.get("min_effort", "low")
    min_rounds = floor_cfg.get("min_rounds")  # None if not set

    rec, problem = _load_artifact(plan_dir, "review-decision")
    if rec is None:
        # Missing artifact: the requires-loop handles the presence check; here
        # we report the floor-specific reason (the caller already blocked on the
        # missing artifact; this path is reachable when floor is called standalone).
        return (
            "stage floor ON but could not read the review-decision artifact "
            "(%s) — cannot check effort/rounds" % problem
        )

    # -- effort check --------------------------------------------------------
    effort = rec.get("effort")
    if effort is None:
        return (
            "floor ON requires review-decision.effort >= %s; missing = block. "
            "Set effort in the review-decision artifact (low|medium|high|xhigh|max)."
            % min_effort
        )
    effort_rank = _EFFORT_RANK.get(effort, -1)
    min_rank = _EFFORT_RANK.get(min_effort, 0)
    if effort_rank < min_rank:
        return (
            "floor ON requires review-decision.effort >= %s; "
            "artifact has effort=%s (rank %d < %d) — block. "
            "Re-run review with effort >= %s or turn the floor off."
            % (min_effort, effort, effort_rank, min_rank, min_effort)
        )

    # -- rounds check --------------------------------------------------------
    if min_rounds is not None:
        rounds_run = rec.get("rounds_run")
        try:
            rounds_val = int(rounds_run) if rounds_run is not None else None
        except (TypeError, ValueError):
            # non-integer rounds_run is treated as missing → block (fail-closed)
            rounds_val = None
        if rounds_val is None or rounds_val < int(min_rounds):
            actual = rounds_run if rounds_run is not None else "missing"
            return (
                "floor ON requires review-decision.rounds_run >= %d; "
                "artifact has rounds_run=%s — block. "
                "Run the full %d review rounds or turn the floor off."
                % (min_rounds, actual, min_rounds)
            )

    return None


def _rule_scan_consistency(plan_dir: Path):
    """Cross-check the review-rules layer's rule-scan.json when it is PRESENT.

    Absent → None (no-op; the gate behaves exactly as before). Present → it is
    validated (required fields, verdict enum, per-violation severity enum) and a
    CONTRADICTION is refused: if any violation is `critical`, the rule-scan's OWN
    verdict must be BLOCKED, and a present review-decision must not be PASS or
    PASS_WITH_RISK. This is the present-but-contradictory case only; a reviewer
    who never produced a rule-scan is an accepted AI-applied gap the gate does
    not force."""
    p = _artifact_path(plan_dir, "rule-scan")
    if not p.is_file():
        return None
    rec, problem = _load_artifact(plan_dir, "rule-scan")
    if rec is None:
        return ("artifact 'rule-scan' %s — fix or remove "
                "%s (see harness/schemas/"
                "artifact-rule-scan.json)" % (problem, p))
    missing = [f for f in _REQUIRED_FIELDS["rule-scan"] if f not in rec]
    if missing:
        return ("artifact 'rule-scan' at %s is missing "
                "required field(s): %s" % (p, ", ".join(missing)))
    # The verdict enum is validated when present so an off-enum value (a typo'd
    # "Passed") fails CLOSED rather than slipping the BLOCKED comparison below.
    if rec.get("verdict") not in ("PASS", "PASS_WITH_RISK", "BLOCKED"):
        return ("artifact 'rule-scan' verdict is %r — must be one of "
                "PASS/PASS_WITH_RISK/BLOCKED" % rec.get("verdict"))
    violations = rec.get("violations")
    if not isinstance(violations, list):
        return "artifact 'rule-scan' field 'violations' must be a list"
    # Severity enum FLOOR (fail-closed): the gate keys off the exact token
    # 'critical', so a violation written with an off-enum severity ('high',
    # 'blocker', 'P0', a non-string) would be neither 'critical' nor 'info' and
    # could ride a PASS unseen. Reject any present violation whose normalized
    # severity is not in {critical, info} — the schema enum, enforced here since
    # the gate runs no jsonschema.
    for v in violations:
        if not isinstance(v, dict):
            return "artifact 'rule-scan' has a non-object violation entry"
        sev = str(v.get("severity", "")).strip().lower()
        if sev not in ("critical", "info"):
            return ("artifact 'rule-scan' has a violation with severity %r — must "
                    "be 'critical' or 'info'" % v.get("severity"))
    # Severity matched case/whitespace-insensitively so "Critical"/" critical "
    # cannot bypass.
    has_critical = any(str(v.get("severity", "")).strip().lower() == "critical"
                       for v in violations)
    if not has_critical:
        return _coverage_check(plan_dir, rec)
    # A critical violation makes the artifact's OWN verdict load-bearing: the
    # schema mandates BLOCKED. Enforcing it here catches a self-contradictory
    # rule-scan (critical violations but verdict PASS) regardless of whether a
    # review-decision exists — closing the light-stage (push) gap.
    if rec.get("verdict") != "BLOCKED":
        return ("rule-scan records a critical violation but its own verdict is %r "
                "— a critical violation requires verdict BLOCKED (schema "
                "artifact-rule-scan.json)" % rec.get("verdict"))
    # And a present review-decision cannot soft-accept or pass it.
    review, _rp = _load_artifact(plan_dir, "review-decision")
    if isinstance(review, dict) and review.get("verdict") in ("PASS", "PASS_WITH_RISK"):
        return ("rule-scan records a critical rule violation but review-decision "
                "verdict is %r — a critical violation blocks; set the review "
                "verdict to BLOCKED or resolve the violation before this stage"
                % review.get("verdict"))
    return _coverage_check(plan_dir, rec)


# Generic cross-language fallback: a diff intersecting one of these is structural.
# Mirrors the shipped harness/data/standards.yaml drift.structural_globs; used only
# when neither the env override nor a readable standards.yaml carries the key.
_DEFAULT_STRUCTURAL_GLOBS = (
    "src/**", "lib/**", "packages/**", "internal/**", "services/**",
    "modules/**", "**/schemas/*.json", "**/migrations/**",
)


def _read_drift_section(root):
    """The drift: mapping from the highest-precedence readable source, or None.
    Precedence: $HARNESS_STANDARDS_CONFIG file -> <root>/harness/data/standards.yaml
    -> the shipped standards.yaml beside this module. Fail-open: an unreadable or
    drift-less source falls through; never raises into the gate."""
    candidates = []
    env_cfg = os.environ.get("HARNESS_STANDARDS_CONFIG")
    if env_cfg:
        candidates.append(Path(env_cfg))
    candidates.append(Path(root) / "harness" / "data" / "standards.yaml")
    candidates.append(Path(__file__).resolve().parent.parent / "data" / "standards.yaml")
    for path in candidates:
        try:
            data = _yaml_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 -- missing/malformed source -> next candidate
            continue
        if isinstance(data, dict) and isinstance(data.get("drift"), dict):
            return data["drift"]
    return None


def _load_structural_globs(root):
    drift = _read_drift_section(root)
    if drift:
        globs = drift.get("structural_globs")
        if isinstance(globs, list) and globs:
            picked = [g for g in globs if isinstance(g, str) and g.strip()]
            if picked:
                return picked
    return list(_DEFAULT_STRUCTURAL_GLOBS)


def _architecture_review_consistency(plan_dir: Path, root):
    """Tier-2 presence gate (SHIPPED mechanism, per-repo doc). When the reviewed
    diff is STRUCTURAL -- intersects standards.yaml drift.structural_globs -- a hard
    stage requires review-decision to carry architecture_review.checked==true,
    proof the reviewer loaded docs/system-architecture.md and judged drift.

    Diff source = rule-scan.json:changed_files (the one diff source the coverage
    gate already trusts). Absent rule-scan -> None (no diff source; an accepted gap,
    same philosophy as _rule_scan_consistency). Not structural -> None. Presence-
    gated only -- doc_sha is recorded for audit, never sha-matched at ship, so doc
    churn cannot invalidate a passing review."""
    import scope_match
    rec, _p = _load_artifact(plan_dir, "rule-scan")
    if not isinstance(rec, dict):
        return None
    changed = rec.get("changed_files")
    if not isinstance(changed, list) or not changed:
        return None
    globs = _load_structural_globs(root)
    if not scope_match.scope_matches(globs, changed):
        return None
    review, _rp = _load_artifact(plan_dir, "review-decision")
    ar = review.get("architecture_review") if isinstance(review, dict) else None
    if not (isinstance(ar, dict) and ar.get("checked") is True):
        return ("architecture review missing: the reviewed diff is structural "
                "(matches standards.yaml drift.structural_globs) but review-"
                "decision carries no architecture_review.checked==true. Load "
                "docs/system-architecture.md, judge whether the change respects "
                "the component map / layer boundaries / store & hook contracts, "
                "and record architecture_review{checked, doc_sha, drift[]} in the "
                "review-decision artifact (schema artifact-review-decision.json).")
    return None


def check_stage(stage, root, plan_dir=None):
    """None = pass; string = block reason. Soft/unknown stages never block.

    plan_dir: when given, judge THAT plan dir directly — bypasses the global
    newest-in_progress resolver (PR-agnostic; the remote receipts-gate passes the
    dir it resolved from the diff, red-team H3). None = resolve as before, so every
    local caller is unchanged (byte-for-byte)."""
    policy = load_policy()["stages"].get(stage)
    if not isinstance(policy, dict) or not policy.get("hard"):
        return None

    # push opts in (allow_completed_plan) so a close-then-push anchors the
    # freshly-closed plan instead of blocking as no-active-plan.
    allow_completed = bool(policy.get("allow_completed_plan", False))
    if policy.get("require_plan", True):
        plan_dir = plan_dir if plan_dir is not None else resolve_active_plan(
            root, allow_completed=allow_completed)
        if plan_dir is None:
            return (
                "hard stage %r needs an active plan but none resolved. Three "
                "exits: (1) create a plan under plans/ with `status: "
                "in_progress` frontmatter; (2) set HARNESS_ACTIVE_PLAN to the "
                "plan dir; (3) set `require_plan: false` for this stage in "
                "harness/data/stage-policy.yaml (tracked in git)" % stage
            )
    else:
        plan_dir = plan_dir if plan_dir is not None else resolve_active_plan(
            root, allow_completed=allow_completed)

    for kind in policy.get("requires") or []:
        if plan_dir is None:
            return ("hard stage %r requires artifact %r but no active plan "
                    "dir is resolvable to hold it" % (stage, kind))
        reason = _check_artifact(plan_dir, kind, root=root, stage=stage)
        if reason:
            # Personal-first: no break-glass override — a missing receipt blocks
            # the hard stage outright (fix the receipt; local enforcement is
            # advisory post-P7, remote CI is the hard layer).
            return reason

    # Every OTHER phase's snapshot, not just the current one. Scoped to stages that
    # already require `verification` — a stage that does not ask for a verdict at all
    # has no business judging earlier phases' verdicts. Runs after the requires loop
    # so the current phase is judged first and its (more actionable) reason wins.
    if plan_dir is not None and "verification" in (policy.get("requires") or []):
        sweep_reason, _n_phases = _phase_snapshot_sweep(plan_dir)
        if sweep_reason:
            return sweep_reason

    # Stage floor: self-discipline effort/rounds check (opt-in, fail-soft).
    # Called after the requires loop so the presence check already ran. Only
    # fires on hard stages (policy.get("hard") is already confirmed above).
    if plan_dir is not None:
        floor_reason = _check_stage_floor(plan_dir, stage, root)
        if floor_reason:
            return floor_reason

    # Runs on every hard stage regardless of `requires:` — rule-scan is never a
    # required artifact, but a present-and-contradictory one still blocks.
    if plan_dir is not None:
        consistency = _rule_scan_consistency(plan_dir)
        if consistency:
            return consistency

    # Tier-2 architecture_review presence gate: a structural diff (per config
    # globs) must carry review-decision.architecture_review.checked==true. Scoped
    # to stages that REQUIRE review-decision (pr/merge/ship/deploy) -- demanding it
    # at push (which only requires verification) would block honest work, since the
    # review-decision artifact legitimately does not exist there yet.
    if plan_dir is not None and "review-decision" in (policy.get("requires") or []):
        arch = _architecture_review_consistency(plan_dir, root)
        if arch:
            return arch

    # Terminal-stage completeness: ship/deploy "release the work", so the plan must
    # have reached N/N phases (every node's declared `post` present, verdict-gated
    # on verification-*.json — derive_plan_completion is the single counter). NOT on
    # push/pr/merge: those run mid-cook and demanding completeness there blocks oan
    # (C2). plan_dir None (solo require_plan:false) is guarded (C7); any raise
    # degrades to no-block (C3 — the pre-push transport is fail-closed, so a new
    # branch that could raise MUST swallow it here, not just at the return).
    if stage in {"ship", "deploy"} and plan_dir is not None:
        try:
            import derive_plan_completion as dpc
            import plan_graph
            st = dpc.completion_state(plan_dir)
            # Only assess completeness when there is a graph with nodes: n_total == 0
            # means no sidecar (or an empty one), which the sidecar-mandatory gates
            # (plan_approval + cook Step 0.5) already govern — "N/N" is meaningless
            # at N=0, so this branch abstains rather than inventing a new block.
            if not st["complete"] and st["n_total"] > 0:
                graph = plan_graph.parse_phase_graph(plan_dir)
                missing = (sorted(plan_graph._all_nodes(graph) - st["passed_phases"])
                           if "error" not in graph else [])
                return ("%s blocked: plan %r is not complete (%s). Nodes missing "
                        "evidence: %s. Each phase must emit verification-<phase>.json "
                        "carrying a `phase: <node-id>` field — check that the "
                        "verification has the `phase` field set."
                        % (stage, plan_dir.name, st["reason"],
                           ", ".join(missing) or "unknown"))
        except Exception:
            return None
    return None


def main(argv=None):
    """Producer-side CLI. The gate hook does NOT shell out here — this is a
    convenience entry for hs:test/hs:cook to self-check before a hard stage."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="artifact_check",
        description="harness artifact checks (producer-side CLI)")
    parser.add_argument(
        "--validate-verification", metavar="PLAN_DIR",
        help="structural well-formedness check of a plan's verification "
             "artifact; exit 1 (not 2) on problems — this is a producer check, "
             "not a compliance gate")
    parser.add_argument("--root", default=None,
                        help="repo root for test-policy resolution (default: cwd)")
    args = parser.parse_args(argv)
    if args.validate_verification:
        ok, problems = validate_verification_wellformed(
            args.validate_verification, root=args.root)
        if ok:
            print("verification well-formed: %s" % args.validate_verification)
            return 0
        sys.stderr.write(
            "verification NOT well-formed (%s):\n" % args.validate_verification)
        for p in problems:
            sys.stderr.write("  - %s\n" % p)
        return 1
    parser.error("no action requested (try --validate-verification <plan_dir>)")


if __name__ == "__main__":
    sys.exit(main())
