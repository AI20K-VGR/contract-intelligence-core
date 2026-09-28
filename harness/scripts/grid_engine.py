#!/usr/bin/env python3
"""grid_engine.py — thin CLI over the tầng-1 grid-planning package
(``harness/scripts/grid/``). Five subcommands:

  preregister — the pre-registration PRODUCER: an author-declared rules-in
            file -> a frozen, hash-verified ``--rules`` sidecar plus the
            ``grid_ruleset_hash:`` anchor line appended into the plan body.
            0-token, deterministic. Run this BEFORE the plan is approved so
            the freeze sits under the same content a human clicks Approve
            on; ``expand``/``review --rules`` are the consumer side.
  build   — the planner axes module + density_tier -> an all-SKELETON grid.
            0-token, deterministic.
  expand  — skeleton -> the expansion loop, an optional injected invoker
            (default None -> every cell degrades to an attested STUB,
            deterministic and finite).
  review  — grid -> verdict. Deterministic invariant+confab pass, an
            optional injected advisor (default None). Exit 2 on a `reject`
            verdict ONLY when ``--gate`` (gate-producer mode) is set —
            mirrors the harness hook exit-code discipline; a plain
            (non-gate) invocation always exits 0 so a human can inspect a
            reject verdict without the CLI itself treating it as a failure.
  emit    — grid (+ verdict, computed inline unless ``--verdict`` is given)
            -> the ``coverage-grid`` gate artifact, written through
            ``artifact_io.stamp_and_write`` into
            ``plans/<active>/artifacts/coverage-grid.<json|yaml>``.

--auto landmine boundary (hard, CLAUDE.md two-tier constraint): ``--auto``
opts ``build`` into ALSO running the fill loop after the skeleton is built
(one shot skeleton+fill). It is OPT-IN and default OFF: a bare ``build``
invocation NEVER implies it, and nothing in this CLI or any cook/gate
autopilot path ever sets it automatically — only a human explicitly passing
the flag runs the fill. ``--max-iterations N`` overrides the run's resolved
``budget.iterations_max`` outright (widen or narrow — see
``_resolve_max_iterations``); absent, the cap is the density_tier default OR the
grid's own cell count, whichever is larger, clamped down again only by the
density_tier's own token budget when that budget still permits at least the density_tier
default. The loop also always self-terminates on its own deterministic
stop-reasons (SSOT: ``harness.scripts.grid.stopping.StopReason`` — never
re-listed here so this docstring can't drift out of sync with the enum
again), so even ``--auto``
with no injected model is a bounded, finite, all-STUB run — a human-invoked
capped tool, never an unattended token-burning driver. ``expand`` also
accepts ``--auto`` for CLI surface parity with ``build``, but it is a no-op
there: ``expand`` already
IS the explicit "run the loop" subcommand, so a bare ``--grid`` (no
``--auto``) already runs the same bounded, deterministic loop.

Invoker/advisor injection (``--invoker``/``--advisor mod:func``) resolves via
``importlib`` only — never ``eval``/``exec``. This is a dev-grade seam: the
imported callable runs in-process with this CLI's full privileges, so only
point it at a module you trust. Default is None (no injection), which keeps
every subcommand runnable and testable without any model.

Default filler (opt-in, still no new model client): ``--invoker
grid_fill_replay:invoke`` plugs in the shipped replay invoker
(``harness/scripts/grid_fill_replay.py``) without writing a new model
client — it relays raw per-cell content from a JSON file a ``@grid-filler``
subagent (or any other writer honoring the same contract) produced earlier,
and every relayed response still runs through the SAME anti-confab
validation in ``expand_cell`` as any other invoker. The source file path is
``HARNESS_GRID_FILL_SRC`` when set, else the active plan's own
``artifacts/grid-fill-src.json``. This is still opt-in only: a bare
``expand``/``build --auto`` with no ``--invoker`` never reads that file and
stays all-STUB, unchanged.

Never ``import orchestrator`` — this is the independent tầng-1 copy; the
tầng-2 grid engine is referenced only as the string ``orchestrator/grid`` in
the emitted artifact's ``cross_ref`` field (provenance for a future merge,
never a code dependency).
"""
import argparse
import dataclasses
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

import yaml_io

import artifact_check  # noqa: E402 — bare sibling-module import (scripts/ on sys.path)
from feature_checklist import load_checklist  # noqa: E402 — bare sibling-module import

from grid import artifact as grid_artifact  # noqa: E402
from grid import ca  # noqa: E402
from grid import costing  # noqa: E402
from grid.diff_attest import compute_feature_diff  # noqa: E402
from grid.axes import (  # noqa: E402
    build_executor_axes,
    build_planner_axes,
    guardrail_rows,
    strength_config,
)
from grid.density import density_policy  # noqa: E402
from grid.loop import GridLoopConfig, run_grid_loop  # noqa: E402
from grid.preregister import (  # noqa: E402
    _KNOWN_VERDICTS,
    _validate_combo_shape,
    LocalRule,
    MalformedConstraintRuleError,
    dump_frozen_ruleset,
    freeze_ruleset,
    load_frozen_ruleset,
    load_universal_rules,
    render_ruleset_section,
    verify_ruleset_hash_matches_plan,
)
from grid.review import GridReviewInput, load_axis_selection, review_grid  # noqa: E402
from grid.skeleton import (  # noqa: E402
    build_grid_skeleton,
    cells_to_rows,
    extend_grid_skeleton,
)
from grid.stopping import compute_coverage_ratio  # noqa: E402
from grid.types import Grid  # noqa: E402

_EVIDENCE_PREFIX_CHOICES = tuple(sorted(grid_artifact.EVIDENCE_PREFIX_SETS))


def _load_dotted(spec):
    """Resolve ``"module.path:attr"`` via ``importlib`` (never ``eval``).
    Raises ``ValueError`` with an actionable message on a bad path — the
    caller turns that into a clean stderr + non-zero exit, never a bare
    traceback."""
    mod_name, sep, attr_name = spec.partition(":")
    if not sep or not mod_name or not attr_name:
        raise ValueError(
            "invalid seam spec %r — expected 'module.path:attr'" % spec)
    try:
        mod = importlib.import_module(mod_name)
    except ImportError as e:
        raise ValueError("cannot import module %r: %s" % (mod_name, e)) from e
    try:
        return getattr(mod, attr_name)
    except AttributeError as e:
        raise ValueError(
            "module %r has no attribute %r: %s" % (mod_name, attr_name, e)) from e


def _bind_invoker_root(spec, root):
    """If the ``--invoker`` module exposes a ``set_root(path)`` hook (the
    convention ``grid_fill_replay.set_root`` documents), call it with the
    resolved ``--root`` so a root-aware invoker reads the SAME root
    ``--validate --root X``/``--rules --root X`` already honour, instead of
    silently falling back to ``Path.cwd()`` -- the divergence measured
    against a two-project fixture (a wrong-project fill source with zero
    warning). A no-op for any invoker that does not define the hook: this
    never widens the ``LlmInvoker`` Callable seam itself, only opts a
    consenting module into a root it could not otherwise reach."""
    mod_name, _, _ = spec.partition(":")
    try:
        mod = importlib.import_module(mod_name)
    except ImportError:
        return
    setter = getattr(mod, "set_root", None)
    if callable(setter):
        setter(Path(root) if root else Path.cwd())


def _resolve_max_iterations(
    override, density_tier_default, cell_count=None,
    depth_tokens_max=None, per_cell_token_cap=None,
):
    """The run's static iteration ceiling.

    ``density_tier_default`` is a FLOOR, never something a real grid gets clamped
    below: when ``cell_count`` (the grid's own cell total) exceeds the density_tier
    default, the cap grows to ``cell_count`` — a 51-cell MID grid capped at
    the MID density_tier's 40-iteration default used to strand 11 cells at
    ITERATION_CAP with no way to reach them even via ``--max-iterations``
    (``min()`` could only tighten, never loosen).

    ``depth_tokens_max``/``per_cell_token_cap`` (when both given) derive a
    SECONDARY ceiling (``depth_tokens_max // per_cell_token_cap``) that can
    pull the cap back down — but only when that derived ceiling is still
    AT OR ABOVE ``density_tier_default``. A derived ceiling below the density_tier default
    is ignored outright rather than applied at a floored value: since
    ``grid/stopping.py`` now stops a run for real once
    ``depth_tokens_used >= depth_tokens_max`` (the token-derived ceiling
    here is a defensive secondary belt, not the primary spend fence
    anymore), a secondary belt that tightens the cap below what the density_tier
    already permitted would be a regression, not a safeguard. Under the
    shipped SSOT this ceiling never actually bites for LOW/MID/HIGH (their
    derived ceiling sits under their own density_tier default) — it stays live for
    a future density_tier whose numbers land the other way.

    ``override`` (``--max-iterations``) always wins outright when given —
    it can widen OR narrow past everything above. The final result is
    clamped to >= 1: a 0 or negative override used to yield an all-SKELETON
    grid, which is a gate-evasion shape in its own right.
    """
    base = density_tier_default
    if cell_count is not None:
        base = max(base, cell_count)
    if depth_tokens_max and per_cell_token_cap:
        token_ceiling = depth_tokens_max // per_cell_token_cap
        if token_ceiling >= density_tier_default:
            base = min(base, token_ceiling)
    resolved = base if override is None else override
    return max(1, resolved)


def _cap_cell_count_margin(grid):
    """The ``cell_count`` value real build/expand call sites pass to
    ``_resolve_max_iterations`` — the grid's own cell total PLUS ONE, never
    the bare count.

    Bare ``len(grid.cells)`` reproduces the stranded-cells bug in a new
    shape: with the cap set to EXACTLY the cell count, the loop's
    should_continue call right after the last cell finishes sees
    ``budget.iterations == budget.iterations_max`` AND an empty queue in
    the SAME check — and ``iteration-cap`` outranks ``queue-empty`` in
    priority (grid/stopping.py), so a run that touched every single cell
    still reports the misleading ``iteration-cap`` as its terminal reason.
    The +1 margin costs nothing (the loop still halts via queue-empty at
    the true last cell, never actually spending the extra iteration) and
    makes the reported stop reason honest. ``_resolve_max_iterations``
    itself stays untouched by this margin — its own cell_count contract is
    pinned exactly
    at the raw count."""
    return len(grid.cells) + 1


def _load_grid_file(path):
    """Read a grid file, raising only what its three callers already catch.

    Each caller wraps this in `except (OSError, ValueError, KeyError)`, and
    `Grid.from_dict` on a JSON value that is not an object raises TypeError,
    which is none of them. Measured on `[1, 2, 3]`: `expand`, `review` and
    `emit` each printed a raw traceback at rc=1 — off the ladder, in the three
    commands whose error handling was written to keep them on it. Narrowed here
    rather than widened in three tuples: one shape check, one place, and a
    caller that adds a fourth entry point gets the same behaviour for free."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("a grid file must hold a JSON object, got %s"
                         % type(raw).__name__)
    return Grid.from_dict(raw)


def _emit_json(obj, out_path=None):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    if out_path:
        Path(out_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _die(msg, code=2):
    sys.stderr.write("grid_engine: error: %s\n" % msg)
    return code


def _resolve_plan_path(args, root):
    """Resolve the plan.md this call anchors to -- the single plan-resolution
    rule shared by ``_load_frozen_rules`` and ``_cmd_emit``.

    ``--plan <path>`` wins outright when given: that exact file is used, with
    NO requirement that it be ``in_progress`` (or even the plan
    ``artifact_check.resolve_active_plan`` would pick). Freezing a ruleset
    happens BEFORE approval (build -> freeze -> fill), so requiring an
    already-approved active plan inverted the intent -- it blocked the
    legitimate pre-approval freeze and permitted the post-approval mint (see
    ``_load_frozen_rules``). No ``--plan`` -> fall back to today's
    active-plan resolution. Neither resolves -> die naming BOTH ways out.

    The resolved path MUST BE ``plan.md`` itself -- the one file
    ``plan_approval.plan_hash``/``file_hashes`` actually cover. A directory
    is accepted and resolved to ``<dir>/plan.md`` (friendlier and
    unambiguous); anything else is refused outright naming why. Before this
    check, ``--plan`` accepted ANY file (``is_file()`` only) -- a decoy sitting
    beside a real plan.md (e.g. ``notes.md``) could carry its own
    ``grid_ruleset_hash:`` anchor line and verify cleanly, because the hash
    was checked against the decoy's own content, never against anything
    ``plan_approval`` hashes. Anchoring the freeze anywhere but plan.md is
    therefore not a weaker version of the real freeze -- it is invisible to
    approval entirely, so minting a forged ruleset into a decoy file and
    pointing ``--rules``/``--plan`` at it used to mint credit into a plan a
    human never actually reviewed.

    Returns ``(plan_path, exit_code_or_None)`` -- a non-None exit code means
    ``_die`` already wrote the reason to stderr, and the caller must return
    it immediately."""
    given_plan = getattr(args, "plan", None)
    if given_plan:
        plan_path = Path(given_plan)
        if plan_path.is_dir():
            plan_path = plan_path / "plan.md"
        elif plan_path.name != "plan.md":
            return None, _die(
                "--plan %r must be plan.md itself or its containing "
                "directory (got a file named %r) -- the plan-approval hash "
                "only ever covers plan.md (+ phase-*.md + plan-graph.yaml), "
                "so anchoring a ruleset freeze to a differently-named file "
                "would verify against content nobody hashes"
                % (given_plan, plan_path.name))
        if not plan_path.is_file():
            return None, _die("--plan %r does not exist" % str(plan_path))
        return plan_path, None

    root_path = Path(root) if root else Path(".")
    plan_dir = artifact_check.resolve_active_plan(root_path)
    if plan_dir is None:
        return None, _die(
            "no plan resolved: pass --plan <path/to/plan.md>, or set an "
            "active plan via HARNESS_ACTIVE_PLAN, or have a plans/*/plan.md "
            "with `status: in_progress` under %s/plans" % root_path
        )
    return plan_dir / "plan.md", None


def _plan_status(plan_path):
    """The plan's own frontmatter ``status:`` (quote/dash-normalized like
    ``artifact_check.resolve_active_plan`` does), or None when
    unreadable/absent."""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return None
    status = artifact_check._frontmatter_status(text)
    return status.strip("'\"").replace("-", "_") if status else None


def _warn_if_unapproved(plan_path):
    """Honest-limitation stderr line (never a die) when a ``--rules`` freeze
    is being verified against a plan that is not (yet) ``in_progress``. This
    is the intended pre-approval freeze order, not an error -- the anti-fraud
    barrier rests on the human reviewing the rendered rule table at Approve
    time (the content-hash anchor), not on this command's state check."""
    status = _plan_status(plan_path)
    if status == "in_progress":
        return
    sys.stderr.write(
        "grid_engine: warning: UNAPPROVED — N/A credit is being computed "
        "against a ruleset frozen into an UNAPPROVED plan (%r, status: %r). "
        "This is the intended pre-approval freeze order — the human "
        "approving this plan will see the rendered rule table in the plan "
        "body. Anti-fraud rests on that review, not on this command.\n"
        % (str(plan_path), status)
    )


def _load_frozen_rules(args):
    """Load + hash-verify a ``--rules`` sidecar against the plan.md body
    ``_resolve_plan_path`` resolves (the SAME content the drift guard
    hashes) before threading it anywhere. Returns ``(frozen_ruleset_or_None,
    exit_code_or_None)`` -- a non-None exit code means ``_die`` already
    wrote the reason to stderr, and the caller must return it immediately
    without touching the grid. No ``--rules`` -> ``(None, None)``, the
    fail-closed default (0 N/A credit) unchanged from every caller
    predating this sidecar seam.

    Security invariant kept: the hash is verified against ``plan.md``'s own
    CONTENT (``verify_ruleset_hash_matches_plan``, which strips frontmatter +
    ``## Phases`` identically to ``plan_approval.plan_hash``) -- a mismatch
    still dies closed. Security invariant DROPPED (deliberately): the plan
    no longer needs to be the approved/in_progress active plan --
    ``_resolve_plan_path`` accepts any ``--plan`` pointer. That state check
    was never what prevented fraud: freezing a ruleset always rewrites the
    plan body (``preregister`` appends the rendered rule table + the
    ``grid_ruleset_hash:`` anchor line), which changes ``plan_hash``, which
    re-opens approval -- a human reviews the rendered rule table before
    Approve either way. The content-hash anchor is the real barrier and is
    unaffected by this change. A plan not yet approved gets the UNAPPROVED
    stderr warning, never a block."""
    if not args.rules:
        return None, None
    try:
        frozen = load_frozen_ruleset(args.rules)
    except MalformedConstraintRuleError as e:
        return None, _die(str(e))

    plan_path, err = _resolve_plan_path(args, getattr(args, "root", None))
    if err is not None:
        return None, err

    _warn_if_unapproved(plan_path)

    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError as e:
        return None, _die("cannot read plan %r: %s" % (str(plan_path), e))
    if not verify_ruleset_hash_matches_plan(frozen, plan_text):
        return None, _die(
            "--rules sidecar hash does not match plan %r "
            "(grid_ruleset_hash line missing/mismatched)" % str(plan_path)
        )
    return frozen, None


# ---- preregister ----

# Matches a whole rendered ``render_ruleset_section`` block (the heading
# through its trailing ``grid_ruleset_hash:`` line) so a re-run replaces the
# section in place instead of appending a duplicate -- idempotent producer.
_RULESET_SECTION_RE = re.compile(
    r"## Grid constraint rules \(frozen\).*?^grid_ruleset_hash:\s*\S+\s*$\n?",
    re.DOTALL | re.MULTILINE,
)


def _load_rules_in_local(doc):
    """Parse the optional ``local_rules:`` list of an author-declared
    rules-in file into ``LocalRule`` objects -- same combo-shape + verdict
    guard as the universal-tier loader (fail-closed, never a silent empty
    list). Entries use the same ``id``/``combo``/``verdict``/``rationale``
    shape as ``constraint_rules.rules``; ``source``/``derived_from`` default
    to marking the rule as author-declared (never derived from a plan step,
    which is what ``derive_local_rules`` is for)."""
    entries = doc.get("local_rules") or []
    if not isinstance(entries, list):
        raise MalformedConstraintRuleError("local_rules must be a list: %r" % entries)
    rules = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise MalformedConstraintRuleError("local_rules entry is not a mapping: %r" % raw)
        rid = raw.get("id")
        combo = raw.get("combo")
        verdict = raw.get("verdict", "forbidden")
        if not rid or not isinstance(combo, dict):
            raise MalformedConstraintRuleError("local_rules entry missing id/combo: %r" % raw)
        _validate_combo_shape(rid, combo)
        if verdict not in _KNOWN_VERDICTS:
            raise MalformedConstraintRuleError("local rule %r has unknown verdict %r" % (rid, verdict))
        rules.append(LocalRule(
            id=rid, combo=dict(combo), verdict=verdict,
            rationale=raw.get("rationale", ""),
            source=raw.get("source", "rules-in"),
            derived_from=raw.get("derived_from", ""),
        ))
    return rules


def _cmd_decide(args):
    """Echo a grid-decision record and (unless --dry-run) append it to the
    plan's append-only ledger. Exists so a skill never has to hand-author a
    throwaway script to reach ``append_grid_decision`` — an improvisation that
    both dogfood sessions performed and that has no business being invented
    fresh at the exact moment a human is being asked to confirm something."""
    from grid.decisions import append_grid_decision, render_decision

    # Every refusal below returns 2 — "this command cannot answer" — like the
    # rest of this CLI. They returned 1, a code the exit ladder gives no meaning
    # to, so a caller checking `rc == 0` read every one of them as success and
    # recorded a decision the ledger never received.
    # UnicodeDecodeError subclasses ValueError, not OSError: a --record holding
    # binary bytes walked straight past an `except OSError` and out as a raw
    # traceback with rc=1, the same off-ladder answer this block exists to end.
    try:
        raw = Path(args.record).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # The read was outside the try below, whose own comment says the point
        # is that a caller sees what to fix instead of a traceback. A missing
        # --record printed a FileNotFoundError stack at the exact moment a human
        # is being asked to confirm something.
        # getattr, not .strerror: UnicodeDecodeError has no such attribute, so
        # reaching for it turned the handler itself into the traceback it was
        # written to prevent.
        sys.stderr.write("grid_engine decide: cannot read --record %s: %s\n"
                         % (args.record, getattr(exc, "strerror", None) or exc))
        return 2
    try:
        rec = json.loads(raw)
    except ValueError as exc:
        sys.stderr.write("grid_engine decide: --record is not valid JSON: %s\n" % exc)
        return 2
    if not isinstance(rec, dict):
        sys.stderr.write("grid_engine decide: --record must be a JSON object\n")
        return 2

    # The closed-vocabulary check lives in render/append and raises before any
    # I/O; surface it as a one-line reason so a caller sees what to fix instead
    # of a traceback, and so a rejected record never half-writes the ledger.
    try:
        rendered = render_decision(rec)
    except ValueError as exc:
        sys.stderr.write("grid_engine decide: %s\n" % exc)
        return 2

    # The echo is I/O too. A record whose text the output encoding cannot carry
    # fails HERE, before the ledger is ever reached. Measured with a lone
    # surrogate in `summary` — legal JSON, illegal UTF-8 — under the default
    # encoding: traceback at rc=1 out of this line.
    try:
        sys.stdout.write(rendered + "\n")
    except (OSError, UnicodeError) as exc:
        sys.stderr.write("grid_engine decide: cannot write the rendered "
                         "decision: %s\n" % exc)
        return 2
    if args.dry_run:
        return 0
    # The write is as capable of failing as the read was, and it fails LATER —
    # after the decision has already gone to stdout. An unguarded
    # `NotADirectoryError` here (--plan naming a file) or `PermissionError`
    # (read-only plan dir) printed a stack at rc=1 underneath a
    # rendered-and-apparently-accepted decision, which reads as recorded and is
    # not. Measured: `--plan <a file>` gave the full decision on stdout, the
    # traceback on stderr, rc=1.
    #
    # `UnicodeError`, not just `OSError`: a lone surrogate that survives to the
    # ledger write raises `UnicodeEncodeError`, which subclasses ValueError.
    # Measured with `PYTHONIOENCODING=utf-8:replace` — stdout took the record,
    # the ledger write raised, and the traceback came out at rc=1 having left
    # an EMPTY `grid-decisions.md` behind, because opening in append mode
    # creates the file before the write fails. That zero-byte file then reads
    # as "a ledger exists" to everything downstream.
    try:
        append_grid_decision(args.plan, rec)
    except (OSError, UnicodeError) as exc:
        sys.stderr.write("grid_engine decide: cannot append to the ledger under "
                         "--plan %s: %s\n" % (args.plan, exc))
        # On stdout, where the decision itself went. A caller reading only
        # stdout saw a complete, accepted-looking decision and no hint that
        # nothing was recorded; the exit code says so but the transcript a
        # human reads does not.
        sys.stdout.write("NOT RECORDED — the decision above was not written to "
                         "the ledger\n")
        return 2
    return 0


def _add_decide_parser(sub):
    p = sub.add_parser(
        "decide",
        help="echo a grid decision + append it to the plan's decisions ledger",
        description="Render a grid-decision record to stdout and append it to "
                    "<plan-dir>/artifacts/grid-decisions.md (append-only, "
                    "never a gate input). Use --dry-run for the mandatory "
                    "echo-to-chat step BEFORE an AskUserQuestion, then re-run "
                    "without it to record the answer -- no silent decisions.",
    )
    p.add_argument("--plan", required=True,
                    help="plan DIRECTORY whose artifacts/grid-decisions.md is appended to")
    p.add_argument("--record", required=True,
                    help="path to a JSON object: {event, summary, detail} -- "
                         "event must be one of the closed vocabulary "
                         "(grid.decisions.EVENT_VOCAB): axis-selection, "
                         "cost-table, user-answer, allow-oversize, escalate, "
                         "auto-escalate, below-floor-hitl, keyword-lint")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="render to stdout only; do not touch the ledger")
    return p


def _add_preregister_parser(sub):
    p = sub.add_parser(
        "preregister",
        help="author-declared rules-in -> frozen --rules sidecar + plan.md hash anchor",
        description="The pre-registration PRODUCER: read an author-declared "
                     "rules-in file, freeze it, write the --rules sidecar "
                     "consumed by expand/review, and append the "
                     "human-readable rule table + hash-anchor line into the "
                     "plan body -- BEFORE the plan is approved, so the "
                     "freeze sits under the same content a human clicks "
                     "Approve on. Idempotent: a re-run replaces the "
                     "previously-appended section instead of duplicating it.",
    )
    p.add_argument("--rules-in", required=True, dest="rules_in",
                    help="author-declared rules YAML: a `constraint_rules:` "
                         "section (identical shape to grid-axes.yaml's own "
                         "section, parsed by the same load_universal_rules) "
                         "plus an optional `local_rules:` list of the same "
                         "id/combo/verdict/rationale shape")
    p.add_argument("--plan", required=True,
                    help="path to the plan.md the freeze hash anchors to; "
                         "its body gains the rendered rule section + "
                         "grid_ruleset_hash: line")
    p.add_argument("--out", default=None,
                    help="sidecar output path (default: "
                         "<plan-dir>/artifacts/grid-preregistration.json)")


def _cmd_preregister(args):
    rules_in_path = Path(args.rules_in)
    try:
        rules_in_text = rules_in_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _die("cannot read --rules-in %r: %s" % (args.rules_in, e))
    try:
        doc = yaml_io.safe_load(rules_in_text) or {}
    except yaml_io.YAMLError as e:
        return _die("--rules-in %r is not valid YAML: %s" % (args.rules_in, e))
    if not isinstance(doc, dict):
        return _die("--rules-in %r must be a YAML mapping" % args.rules_in)

    try:
        universal = load_universal_rules(path=rules_in_path) if "constraint_rules" in doc else []
        local = _load_rules_in_local(doc)
    except MalformedConstraintRuleError as e:
        return _die(str(e))
    if not universal and not local:
        return _die(
            "--rules-in %r declares no rules (need constraint_rules and/or "
            "local_rules)" % args.rules_in
        )

    frozen = freeze_ruleset(universal, local)

    plan_path = Path(args.plan)
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except OSError as e:
        return _die("cannot read --plan %r: %s" % (args.plan, e))

    out_path = Path(args.out) if args.out else plan_path.parent / "artifacts" / "grid-preregistration.json"
    sidecar_text = json.dumps(dump_frozen_ruleset(frozen), indent=2, ensure_ascii=False) + "\n"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(sidecar_text, encoding="utf-8")
    except OSError as e:
        return _die("cannot write sidecar %r: %s" % (out_path, e))

    section = render_ruleset_section(frozen)
    if _RULESET_SECTION_RE.search(plan_text):
        new_plan_text = _RULESET_SECTION_RE.sub(section + "\n", plan_text, count=1)
    else:
        new_plan_text = plan_text.rstrip("\n") + "\n\n" + section + "\n"
    if not verify_ruleset_hash_matches_plan(frozen, new_plan_text):
        return _die(
            "preregister could not anchor the ruleset hash into %r -- a "
            "stray grid_ruleset_hash line outside a frozen-rules section "
            "may be shadowing it; remove it and re-run" % args.plan
        )
    try:
        plan_path.write_text(new_plan_text, encoding="utf-8")
    except OSError as e:
        return _die("cannot write plan %r: %s" % (args.plan, e))

    print(
        "grid_engine: wrote %s (%d rule%s, hash %s...)"
        % (out_path, len(frozen.rules), "" if len(frozen.rules) == 1 else "s",
           frozen.ruleset_hash[:8])
    )
    return 0


# ---- build ----

def _add_build_parser(sub):
    p = sub.add_parser(
        "build",
        help="axes + density_tier -> all-SKELETON grid (0-token, deterministic)",
        description="Build a planner grid skeleton. Deterministic and "
                     "0-token: no LLM call anywhere unless --auto is passed.",
    )
    p.add_argument("--agent", required=True, help="planner | qa | executor")
    p.add_argument("--density-tier", dest="density_tier", required=True,
                   choices=["LOW", "MID", "HIGH"])
    p.add_argument("--strength", type=int, default=None,
                    help="CA strength t (breadth axis, independent of "
                         "--density-tier's depth budget). Absent -> "
                         "DEFAULT_STRENGTH_T (t2, CLI back-compat).")
    p.add_argument("--plan-id", default=None)
    p.add_argument("--task-id", default=None)
    p.add_argument("--feature", action="append", default=None,
                    help="repeatable; at least one required (axis values "
                         "must come from the plan, never be hand-typed)")
    p.add_argument("--layer", action="append", default=None)
    p.add_argument("--lifecycle", action="append", default=None)
    p.add_argument("--risk-class", action="append", default=None, dest="risk_class")
    p.add_argument("--stakeholder", action="append", default=None)
    # Executor micro-grid axes (--agent executor). Only --step is required;
    # the other five fall back to the shipped defaults, same as the planner
    # side. Without these the documented micro-grid recipe had no way to
    # supply its one mandatory input.
    p.add_argument("--step", action="append", default=None,
                    help="repeatable; required for --agent executor (axis "
                         "values must come from the phase, never be "
                         "hand-typed)")
    p.add_argument("--precondition", action="append", default=None)
    p.add_argument("--side-effect", action="append", default=None,
                    dest="side_effect")
    p.add_argument("--failure-mode", action="append", default=None,
                    dest="failure_mode")
    p.add_argument("--rollback", action="append", default=None)
    p.add_argument("--verification", action="append", default=None)
    p.add_argument("--axes-json", default=None,
                    help="a JSON object of axis-builder inputs for the "
                         "chosen --agent (literal, or @path/to/file.json); "
                         "merges with / overrides --feature/--step etc.")
    p.add_argument("--now", default=None, help="ISO-8601 override for "
                    "created_at (deterministic tests)")
    p.add_argument("--out", default=None, help="write grid JSON here "
                    "instead of stdout")
    p.add_argument("--auto", action="store_true", default=False,
                    help="OPT-IN, default OFF. When set, ALSO runs the "
                         "expander+loop fill after building the skeleton — "
                         "never implied by a bare `build`, never set by cook/gate "
                         "autopilot. With no --invoker wired, every cell "
                         "degrades to an attested STUB and the run still "
                         "halts finite (bounded by the density_tier's iteration cap "
                         "or --max-iterations, never unattended).")
    p.add_argument("--max-iterations", type=int, default=None, dest="max_iterations",
                    help="only meaningful with --auto; overrides the "
                         "resolved budget.iterations_max OUTRIGHT (widens "
                         "OR narrows the density_tier/cell-count-derived "
                         "default), clamped to >= 1 -- never a min() cap "
                         "(see _resolve_max_iterations)")
    p.add_argument("--invoker", default=None,
                    help="only meaningful with --auto: 'module:attr' LLM "
                         "invoker resolved via importlib (never eval); the "
                         "shipped default filler is "
                         "'grid_fill_replay:invoke' (replays a "
                         "@grid-filler-authored JSON file through the same "
                         "anti-confab seam, no new model client)")
    p.add_argument("--allow-oversize", action="store_true", default=False,
                    dest="allow_oversize",
                    help="permit a build whose skeleton row count exceeds "
                         "the absolute row guardrail (grid-strength.yaml). "
                         "Without it, an over-guardrail build REFUSES "
                         "(emits the build receipt, exits non-zero) instead "
                         "of silently degrading — mirrors expand's "
                         "--allow-oversize semantics.")


def _strength_label(t, ladder):
    """Human-readable strength-ladder level key (e.g. ``"t3"``) for the
    receipt's ``strength`` field. Falls back to ``"t<N>"`` when ``t`` isn't
    on the shipped ladder (e.g. a strength above the current t2/t3 tiers) —
    never raises, since an unladdered strength is still a valid CA strength
    to build at."""
    for level, node in ladder.items():
        if node.get("strength") == t:
            return level
    return "t%d" % t


# --agent decides WHICH axis universe a build uses. Every value other than
# "executor" is a planner-family agent (planner, qa) and keeps the planner
# axes, so this is a widening, not a re-routing of existing behaviour.
_EXECUTOR_AGENT = "executor"

_PLANNER_CLI_INPUTS = (
    ("feature", "features"),
    ("layer", "layers"),
    ("lifecycle", "lifecycle"),
    ("risk_class", "risk_classes"),
    ("stakeholder", "stakeholders"),
)

_EXECUTOR_CLI_INPUTS = (
    ("step", "steps"),
    ("precondition", "preconditions"),
    ("side_effect", "side_effects"),
    ("failure_mode", "failure_modes"),
    ("rollback", "rollbacks"),
    ("verification", "verifications"),
)


def _cmd_build(args):
    # `--agent executor` was accepted, stamped into the record, and then handed
    # PLANNER axes: the artifact's own agent field contradicted its shape, and
    # the executor micro-grid the cook reference documents (and
    # `--require-phase-grids` refuses to close a plan without) could not be
    # produced at all — --axes-json's only executor key was rejected by the
    # planner validator too. Route the axis builder off --agent, and expose
    # each builder's own inputs as flags.
    executor = args.agent == _EXECUTOR_AGENT
    build_axes = build_executor_axes if executor else build_planner_axes
    cli_inputs = _EXECUTOR_CLI_INPUTS if executor else _PLANNER_CLI_INPUTS

    inputs = {}
    if args.axes_json:
        raw = args.axes_json
        if raw.startswith("@"):
            try:
                raw = Path(raw[1:]).read_text(encoding="utf-8")
            except OSError as e:
                return _die("cannot read --axes-json %r: %s" % (args.axes_json, e))
        try:
            inputs.update(json.loads(raw))
        except ValueError as e:
            return _die("cannot parse --axes-json %r: %s" % (args.axes_json, e))
    for attr, key in cli_inputs:
        value = getattr(args, attr, None)
        if value:
            inputs.setdefault(key, list(value))

    try:
        axes = build_axes(inputs)
    except ValueError as e:
        return _die(str(e))

    grid_input = {
        "agent": args.agent,
        "axes": axes,
        "density_tier": args.density_tier,
        "plan_id": args.plan_id,
        "task_id": args.task_id,
    }
    if args.strength is not None:
        grid_input["strength"] = args.strength
    if args.now:
        grid_input["now"] = args.now
    try:
        grid = build_grid_skeleton(grid_input)
    except ValueError as e:
        return _die(str(e))

    # Guardrail: count the SKELETON's exact row cost (0-token, deterministic
    # — costing.build_receipt delegates to ca.greedy_ca, never re-derives its
    # own count) and compare against the absolute row guardrail BEFORE any
    # --auto fill work. An over-guardrail build REFUSES unless the caller
    # opts in via --allow-oversize; it never auto-degrades strength or drops
    # rows to fit (grid-mode.md's documented build contract).
    shape = [len(a.values) for a in axes]
    ladder = strength_config()["strength_ladder"]
    ship_strengths = sorted(node["strength"] for node in ladder.values())
    receipt = costing.build_receipt(
        shape=shape,
        strength=_strength_label(grid.strength, ladder),
        t=grid.strength,
        guardrail_rows=guardrail_rows(),
        ship_strengths=ship_strengths,
    )
    if receipt["over"] and not args.allow_oversize:
        text = costing.emit_receipt(receipt, out_path=args.out)
        if not args.out:
            print(text)
        return 2

    stop_reason = None
    if args.auto:
        invoker = None
        if args.invoker:
            try:
                invoker = _load_dotted(args.invoker)
            except ValueError as e:
                return _die(str(e))
        policy = density_policy(grid.density_tier)
        cap = _resolve_max_iterations(
            args.max_iterations, grid.budget.iterations_max,
            cell_count=_cap_cell_count_margin(grid),
            depth_tokens_max=policy.budget["depth_tokens_max"],
            per_cell_token_cap=policy.per_cell_token_cap,
        )
        grid.budget.iterations_max = cap
        result = run_grid_loop(GridLoopConfig(
            grid=grid, policy=policy, invoke_llm=invoker, max_iterations=cap))
        grid = result.grid
        stop_reason = result.stop_reason

    out = grid.to_dict()
    if stop_reason is not None:
        out["stop_reason"] = stop_reason
    out["build_receipt"] = receipt
    _emit_json(out, args.out)
    return 0


# ---- expand ----

def _add_expand_parser(sub):
    p = sub.add_parser(
        "expand",
        help="skeleton grid -> the expansion loop fill",
        description="Run the bounded expansion loop over a grid file. "
                     "Deterministic and 0-token with no --invoker: every "
                     "cell degrades to an attested STUB and the run still "
                     "halts finite.",
    )
    p.add_argument("--grid", required=True, help="path to a grid JSON file")
    p.add_argument("--invoker", default=None,
                    help="'module:attr' LLM invoker resolved via importlib "
                         "(never eval); default None -> all-STUB. Shipped "
                         "default filler: 'grid_fill_replay:invoke' (replays "
                         "a @grid-filler-authored JSON file — "
                         "HARNESS_GRID_FILL_SRC or the active plan's "
                         "artifacts/grid-fill-src.json — through the same "
                         "anti-confab seam; no new model client)")
    p.add_argument("--max-iterations", type=int, default=None, dest="max_iterations",
                    help="overrides the run's resolved iterations_max "
                         "OUTRIGHT (widens OR narrows the density_tier/"
                         "cell-count-derived default), clamped to >= 1 -- "
                         "never a min() cap (see _resolve_max_iterations)")
    p.add_argument("--policy", default=None,
                    help="override path to the density_tier-density SSOT YAML "
                         "(default: harness/data/grid-density-tier.yaml)")
    p.add_argument("--out", default=None)
    p.add_argument("--auto", action="store_true", default=False,
                    help="accepted for CLI-surface parity with `build "
                         "--auto`; a no-op here — `expand` already IS the "
                         "explicit bounded fill-loop subcommand, so a bare "
                         "--grid (no --auto) already runs the same loop.")
    p.add_argument("--escalate", action="store_true", default=False,
                    help="climb strength t->t+1 immediately (infers current "
                         "t from the grid's own cells via ca.infer_max_t, "
                         "never a stored field). Refuses gracefully — a "
                         "receipt JSON on stdout + a non-zero exit, never a "
                         "bare traceback — when already at max strength "
                         "(t+1 > axis count) or when the full escalated row "
                         "count exceeds the row guardrail without "
                         "--allow-oversize.")
    p.add_argument("--auto-escalate", action="store_true", default=False,
                    dest="auto_escalate",
                    help="OPT-IN, default OFF. After the fill loop stops "
                         "at queue-empty with real (non-zero) coverage "
                         "still unmet, auto-climb exactly one strength "
                         "tier and fill the delta -- never on iteration or "
                         "budget exhaustion, never on an all-STUB "
                         "(zero-depth) grid, never over the row guardrail "
                         "without --allow-oversize.")
    p.add_argument("--allow-oversize", action="store_true", default=False,
                    dest="allow_oversize",
                    help="permit a strength climb whose full row count "
                         "exceeds the absolute row guardrail "
                         "(grid-strength.yaml). Without it, an "
                         "over-guardrail --escalate/--auto-escalate refuses "
                         "instead of silently degrading.")
    p.add_argument("--rules", default=None,
                    help="path to a --rules sidecar (a frozen ruleset JSON "
                         "written by preregister.dump_frozen_ruleset) -- "
                         "hash-verified against whichever plan.md "
                         "_resolve_plan_path resolves (an explicit --plan "
                         "WINS OUTRIGHT over the active-plan resolution; no "
                         "requirement that it be APPROVED/in_progress -- an "
                         "unapproved plan gets a stderr warning, never a "
                         "block; the content-hash anchor is the real "
                         "barrier, not this state check); threads the "
                         "verified FrozenRuleset into "
                         "GridLoopConfig.frozen_rules so a rule:<id> N/A "
                         "attestation can credit COVERAGE_FLOOR. Default "
                         "None -> frozen_rules=None -> 0 N/A credit "
                         "(fail-closed).")
    p.add_argument("--plan", default=None,
                    help="optional explicit pointer to the plan.md (or its "
                         "containing directory) --rules is verified against "
                         "-- WINS OUTRIGHT over active-plan resolution when "
                         "given, with no requirement that it be APPROVED/"
                         "in_progress (see _resolve_plan_path); omitted -> "
                         "falls back to today's active-plan resolution "
                         "(--root)")
    p.add_argument("--root", default=None,
                    help="repo root for active-plan resolution when "
                         "--rules is set (default: cwd)")


def _do_escalate(grid, t_new, delta_count, policy):
    """Mechanically perform one strength climb: extend the cells via
    ``skeleton.extend_grid_skeleton`` then extend the budget ledger —
    BEFORE any iteration-cap resolve reads the ledger, so a downstream
    ``_resolve_max_iterations``/``GridLoopConfig.max_iterations`` sees the
    post-extend numbers (never the pre-extend cap, which would
    shadow-clamp away the delta)."""
    grid = extend_grid_skeleton(grid, t_new)
    grid.budget.iterations_max += delta_count
    grid.budget.depth_tokens_max += delta_count * policy.per_cell_token_cap
    return grid


def _cmd_expand(args):
    try:
        grid = _load_grid_file(args.grid)
    except (OSError, ValueError, KeyError) as e:
        return _die("cannot read grid %r: %s" % (args.grid, e))

    invoker = None
    if args.invoker:
        try:
            invoker = _load_dotted(args.invoker)
        except ValueError as e:
            return _die(str(e))
        _bind_invoker_root(args.invoker, args.root)

    frozen_rules, err = _load_frozen_rules(args)
    if err is not None:
        return err

    policy = density_policy(grid.density_tier, path=args.policy) if args.policy else density_policy(grid.density_tier)

    if args.escalate:
        try:
            shape = [len(a.values) for a in grid.axes]
            rows = cells_to_rows(grid)
            t = ca.infer_max_t(rows, shape)
        except (ValueError, KeyError) as e:
            return _die("cannot escalate malformed grid %r: %s" % (args.grid, e))
        if t + 1 > len(shape):
            receipt = {
                "full_count": len(rows),
                "guardrail_rows": guardrail_rows(),
                "over": False,
                "reason": "already-at-max-strength",
            }
            _emit_json(receipt, args.out)
            return 2
        verdict = costing.escalation_verdict(rows, shape, t + 1, guardrail_rows())
        if verdict["over"] and not args.allow_oversize:
            receipt = {
                "full_count": verdict["full_count"],
                "guardrail_rows": guardrail_rows(),
                "over": verdict["over"],
                "reason": "over-guardrail-without-allow-oversize",
            }
            _emit_json(receipt, args.out)
            return 2
        grid = _do_escalate(grid, t + 1, verdict["delta_count"], policy)

    cap = _resolve_max_iterations(
        args.max_iterations, grid.budget.iterations_max,
        cell_count=_cap_cell_count_margin(grid),
        depth_tokens_max=policy.budget["depth_tokens_max"],
        per_cell_token_cap=policy.per_cell_token_cap,
    )
    grid.budget.iterations_max = cap
    result = run_grid_loop(GridLoopConfig(
        grid=grid, policy=policy, invoke_llm=invoker, max_iterations=cap,
        frozen_rules=frozen_rules))
    grid_out = result.grid
    stop_reason = result.stop_reason

    if (
        args.auto_escalate
        and stop_reason == "queue-empty"
        and compute_coverage_ratio(grid_out) > 0.0
        and compute_coverage_ratio(grid_out, frozen_rules) < policy.coverage_floor
    ):
        try:
            shape = [len(a.values) for a in grid_out.axes]
            rows = cells_to_rows(grid_out)
            t = ca.infer_max_t(rows, shape)
        except (ValueError, KeyError) as e:
            return _die("cannot auto-escalate malformed grid %r: %s" % (args.grid, e))
        if t + 1 <= len(shape):
            verdict = costing.escalation_verdict(rows, shape, t + 1, guardrail_rows())
            if not verdict["over"] or args.allow_oversize:
                grid_out = _do_escalate(grid_out, t + 1, verdict["delta_count"], policy)
                cap2 = _resolve_max_iterations(
                    args.max_iterations, grid_out.budget.iterations_max,
                    cell_count=_cap_cell_count_margin(grid_out),
                    depth_tokens_max=policy.budget["depth_tokens_max"],
                    per_cell_token_cap=policy.per_cell_token_cap,
                )
                grid_out.budget.iterations_max = cap2
                result2 = run_grid_loop(GridLoopConfig(
                    grid=grid_out, policy=policy, invoke_llm=invoker,
                    max_iterations=cap2, frozen_rules=frozen_rules))
                grid_out = result2.grid
                stop_reason = result2.stop_reason

    out = grid_out.to_dict()
    out["stop_reason"] = stop_reason
    _emit_json(out, args.out)
    return 0


# ---- review ----

def _add_review_parser(sub):
    p = sub.add_parser(
        "review",
        help="grid -> verdict, deterministic 0-token invariant+confab pass",
        description="Run the two-tier grid review. Deterministic and "
                     "0-token with no --advisor.",
    )
    p.add_argument("--grid", required=True, help="path to a grid JSON file")
    p.add_argument("--policy", default=None,
                    help="override path to the density_tier-density SSOT YAML "
                         "(default: the grid's own density_tier policy)")
    p.add_argument("--advisor", default=None,
                    help="'module:attr' advisor invoker resolved via "
                         "importlib (never eval); default None -> "
                         "deterministic-only verdict")
    p.add_argument("--axes-src", default=None, dest="axes_src",
                    help="path to a grid-axis-src.json axis-selection file "
                         "(reasons-dict) written by @grid-axis-selector or "
                         "any other producer honoring the same contract; "
                         "threads GridReviewInput.axis_selection. Default "
                         "None -> axis_selection stays None (verdict "
                         "unaffected).")
    p.add_argument("--revalidate", action="store_true", default=False,
                    help="re-drive HIGH cells through a revalidate lane "
                         "AFTER the deterministic pass -- independent of "
                         "--advisor and of --axes-src. Default off; with no "
                         "lane wired this degrades to one soft advisory "
                         "finding, never a hard failure.")
    p.add_argument("--rules", default=None,
                    help="path to a --rules sidecar (a frozen ruleset JSON) "
                         "-- hash-verified against whichever plan.md "
                         "_resolve_plan_path resolves (an explicit --plan "
                         "WINS OUTRIGHT over the active-plan resolution; no "
                         "requirement that it be APPROVED/in_progress -- an "
                         "unapproved plan gets a stderr warning, never a "
                         "block; the content-hash anchor is the real "
                         "barrier, not this state check); threads a "
                         "verified FrozenRuleset into "
                         "GridReviewInput.frozen_rules so a rule:<id> N/A "
                         "attestation can credit COVERAGE_FLOOR, and a "
                         "forged rule:<id> ref becomes a hard reject. "
                         "Default None -> frozen_rules=None -> 0 N/A credit "
                         "(fail-closed).")
    p.add_argument("--plan", default=None,
                    help="optional explicit pointer to the plan.md (or its "
                         "containing directory) --rules is verified against "
                         "-- WINS OUTRIGHT over active-plan resolution when "
                         "given, with no requirement that it be APPROVED/"
                         "in_progress (see _resolve_plan_path); omitted -> "
                         "falls back to today's active-plan resolution "
                         "(--root)")
    p.add_argument("--root", default=None,
                    help="repo root for active-plan resolution when "
                         "--rules is set (default: cwd)")
    p.add_argument("--gate", action="store_true", default=False,
                    help="gate-producer mode: exit 2 on a `reject` verdict "
                         "(mirrors harness hook exit-code discipline). "
                         "Without --gate, a `reject` verdict still exits 0 "
                         "(the verdict is visible in the printed JSON) so a "
                         "human can inspect it without a script treating "
                         "the inspection itself as a failure.")
    p.add_argument("--out", default=None)


def _cmd_review(args):
    try:
        grid = _load_grid_file(args.grid)
    except (OSError, ValueError, KeyError) as e:
        return _die("cannot read grid %r: %s" % (args.grid, e))

    policy = density_policy(grid.density_tier, path=args.policy) if args.policy else density_policy(grid.density_tier)

    advisor = None
    if args.advisor:
        try:
            advisor = _load_dotted(args.advisor)
        except ValueError as e:
            return _die(str(e))

    axis_selection = None
    if args.axes_src:
        try:
            axis_selection = load_axis_selection(args.axes_src)
        except ValueError as e:
            return _die(str(e))

    frozen_rules, err = _load_frozen_rules(args)
    if err is not None:
        return err

    verdict = review_grid(GridReviewInput(
        grid=grid, policy=policy, invoke_advisor=advisor,
        axis_selection=axis_selection, revalidate=args.revalidate,
        frozen_rules=frozen_rules))
    out = dataclasses.asdict(verdict)
    _emit_json(out, args.out)
    if args.gate and verdict.verdict == "reject":
        return 2
    return 0


# ---- emit ----

def _add_emit_parser(sub):
    p = sub.add_parser(
        "emit",
        help="write the coverage-grid gate artifact",
        description="Build (or load) a verdict for --grid and write the "
                     "coverage-grid gate artifact through "
                     "artifact_io.stamp_and_write into "
                     "plans/<active>/artifacts/coverage-grid.<fmt>. "
                     "coverage-grid is advisory-only — this command never "
                     "hard-blocks on a reject verdict.",
    )
    p.add_argument("--grid", required=True, help="path to a grid JSON file")
    p.add_argument("--verdict", default=None,
                    help="path to a precomputed verdict JSON file; when "
                         "absent, review runs inline (deterministic, no "
                         "advisor) against the grid's own density_tier policy")
    p.add_argument("--format", choices=["json", "yaml"], default="json", dest="fmt")
    p.add_argument("--evidence-prefix-set", choices=_EVIDENCE_PREFIX_CHOICES,
                    default=grid_artifact.DEFAULT_EVIDENCE_PREFIX_SET,
                    dest="evidence_prefix_set",
                    help="writer-boundary metadata only — never overrides "
                         "the types.py EVIDENCE_PREFIX_PATTERN invariants/"
                         "confab actually validate against. Default %r is "
                         "the shipped harness-flavored union already in "
                         "types.py." % grid_artifact.DEFAULT_EVIDENCE_PREFIX_SET)
    p.add_argument("--axes-src", default=None, dest="axes_src",
                    help="path to a grid-axis-src.json axis-selection file "
                         "(reasons-dict) written by @grid-axis-selector or "
                         "any other producer honoring the same contract; "
                         "threads the axis-selection receipt into the "
                         "emitted record's axis_selection mark AND (unless "
                         "--verdict is given) into the inline review's "
                         "GridReviewInput.axis_selection. Default None -> "
                         "no mark, verdict unaffected (byte-compat).")
    p.add_argument("--checklist", default=None,
                    help="path to a frozen feature-risk-checklist.json "
                         "(written by feature_checklist.py); hash-verified "
                         "then diffed against the grid's feature axis, "
                         "recording a diff_attest block. Default None -> "
                         "no diff_attest, and a stderr warning that the "
                         "drop-detection pass is inert.")
    p.add_argument("--rules", default=None,
                    help="path to a --rules sidecar (a frozen ruleset JSON) "
                         "-- hash-verified against the plan --plan resolves "
                         "to (or the active plan when --plan is absent); "
                         "threads the verified FrozenRuleset into the "
                         "inline review (unless --verdict is given) AND "
                         "stamps the emitted record's ruleset mark "
                         "({ruleset_hash, rule_count}) so a later audit can "
                         "see which ruleset granted this grid's N/A credit. "
                         "Default None -> no mark, no inline credit.")
    p.add_argument("--plan", default=None,
                    help="optional explicit pointer to the plan.md --rules "
                         "is verified against AND the artifacts/ dir the "
                         "coverage-grid record is written into -- need NOT "
                         "be the approved active plan (see _resolve_plan_path). "
                         "Default None -> falls back to the active plan "
                         "resolved via --root.")
    p.add_argument("--root", default=None,
                    help="repo root for active-plan resolution (default: cwd)")
    p.add_argument("--phase", default=None,
                    help="write an executor PER-PHASE micro-grid to "
                         "coverage-grid-<phase>.<fmt> instead of the macro "
                         "coverage-grid.<fmt> — the plan-level path plan "
                         "approval reads. Default None -> macro path, "
                         "byte-identical to every emit before this flag "
                         "existed. Never pass this for a plan-level "
                         "(planner/qa) grid.")
    p.add_argument("--out", default=None, help="print the stamped record here too")


def _cmd_emit(args):
    if args.phase is not None and (not args.phase or "/" in args.phase or "\\" in args.phase):
        # --phase becomes a literal filename SEGMENT
        # (coverage-grid-<phase>.<fmt>), never a path: an empty value or one
        # containing a path separator either nests the artifact a directory
        # deeper (invisible to count_phase_grids's flat scan of artifacts/)
        # or dies with a raw OSError traceback out of the writer instead of
        # a clean, actionable CLI error at the boundary that owns validating
        # it.
        return _die(
            "--phase %r is not a valid phase id -- it becomes a literal "
            "filename segment (coverage-grid-<phase>.<fmt>), so it must be "
            "non-empty and contain no path separators" % args.phase)

    try:
        grid = _load_grid_file(args.grid)
    except (OSError, ValueError, KeyError) as e:
        return _die("cannot read grid %r: %s" % (args.grid, e))

    axis_sel = None
    axis_mark = None
    if args.axes_src:
        try:
            axis_sel = load_axis_selection(args.axes_src)
        except ValueError as e:
            return _die(str(e))
        src_sha256 = hashlib.sha256(Path(args.axes_src).read_bytes()).hexdigest()
        axis_mark = {"axes": axis_sel.axes, "src_sha256": src_sha256}

    diff_attest = None
    if args.checklist:
        try:
            checklist = load_checklist(args.checklist)
        except ValueError as e:
            return _die(str(e))
        feature_axis = next((ax for ax in grid.axes if ax.id == "feature"), None)
        checklist_source = checklist.get("source", "discover-pass-1")
        if feature_axis is None:
            diff_attest = {
                "dropped": [], "added": [],
                "skipped": "no feature axis to diff",
                "checklist_sha256": checklist["content_sha256"],
                "source": checklist_source,
            }
        else:
            diff = compute_feature_diff(checklist["features"], feature_axis.values)
            diff_attest = {
                "dropped": diff["dropped"], "added": diff["added"],
                "checklist_sha256": checklist["content_sha256"],
                "source": checklist_source,
            }
    else:
        # Warn, never block: the drop-detection mechanism has never
        # once run in a real session because producing the checklist is an
        # optional discover step most plans skip -- making this a hard block
        # would force every grid plan through a discovery workflow, a far
        # bigger process change than the defect warrants. This turns the
        # silent `diff_attest: None` into something visible.
        sys.stderr.write(
            "grid_engine: warning: no feature checklist to diff against — "
            "this grid's feature axis is self-authored, so the "
            "drop-detection pass (diff_attest) is inert. Produce one via "
            "hs:discover (@independent-revalidator + feature_checklist.py "
            "emit), or accept that a silently dropped feature will not be "
            "caught here.\n"
        )

    frozen_rules, err = _load_frozen_rules(args)
    if err is not None:
        return err

    if args.verdict:
        try:
            verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return _die("cannot read verdict %r: %s" % (args.verdict, e))
    else:
        policy = density_policy(grid.density_tier)
        verdict = dataclasses.asdict(review_grid(GridReviewInput(
            grid=grid, policy=policy, axis_selection=axis_sel,
            frozen_rules=frozen_rules)))

    plan_path, err = _resolve_plan_path(args, args.root)
    if err is not None:
        return err
    plan_dir = plan_path.parent

    ruleset_mark = None
    if frozen_rules is not None:
        ruleset_mark = {
            "ruleset_hash": frozen_rules.ruleset_hash,
            "rule_count": len(frozen_rules.rules),
        }

    # Bind the grid to the plan's CONTENT. Imported here rather than at module
    # scope: plan_approval reaches back into grid_emit_guard, and this keeps the
    # engine free of that loop.
    import plan_approval
    try:
        plan_sha256 = plan_approval.plan_hash(plan_dir)
    except OSError as e:
        return _die("cannot hash plan %r for the freshness binding: %s"
                    % (str(plan_dir), e))

    record = grid_artifact.build_coverage_grid_record(
        grid, verdict, evidence_prefix_set=args.evidence_prefix_set,
        axis_selection=axis_mark, diff_attest=diff_attest, ruleset=ruleset_mark,
        plan_sha256=plan_sha256)
    stamped = grid_artifact.write_coverage_grid(plan_dir, record, fmt=args.fmt, phase=args.phase)
    _emit_json(stamped, args.out)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="grid_engine",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_preregister_parser(sub)
    _add_build_parser(sub)
    _add_expand_parser(sub)
    _add_review_parser(sub)
    _add_emit_parser(sub)
    _add_decide_parser(sub)
    return parser


_DISPATCH = {
    "preregister": _cmd_preregister,
    "build": _cmd_build,
    "expand": _cmd_expand,
    "review": _cmd_review,
    "emit": _cmd_emit,
    "decide": _cmd_decide,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return _DISPATCH[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
