#!/usr/bin/env python3
"""partner_companion.py — the ONE chokepoint every ccs partner-lane call
passes through. Twin of gemini_companion.py's partner_call, but
SINGLE-engine BY CONSTRUCTION: ccs itself proxies to whichever
provider profile the caller names, so there is no cross-engine fallback here
— provider picks the destination, never a hardcoded lane, and a down ccs
degrades LOUD rather than silently falling back to a second engine or to
main Claude.

`partner_call(purpose, prompt, provider, ...)` is the single place that:
  1. reads the lane policy (`master: off` -> Inert, no spawn);
  2. validates the provider against LIVE discovery before ever spawning —
     never call ccs blind;
  3. composes the purpose's methodology preamble
     (partner-prompt-templates.yaml, miss -> raw prompt);
  4. WARNS (never blocks) on a secret-looking COMPOSED payload — see the
     HONESTY note below;
  5. drives CcsPrintTransport with retry-on-transient (single lane, no
     cross-engine fallback);
  6. stamps provenance with a `ccs:`-prefixed reviewer_engine so a finding
     never blurs with the gemini lane (`reviewer_engine: gemini`) or main
     Claude;
  7. compares cost to `cost_warn_usd` and stamps/warns when exceeded;
  8. degrades LOUDLY + stamped on a down transport — NEVER a silent
     main-Claude fallback.

HONESTY (verified live via red-team review): the secret-scan at step 4 sees
ONLY the composed prompt STRING. The delegated full-Claude that
`ccs <provider> -p ...` spawns can itself Read files off disk (.env,
~/.ccs/* tokens) and egress them without ever passing this scan — this is a
PROMPT-LEVEL warn, not an egress boundary. `egress_scope:
"whole-repo-readable"` is stamped on every outcome so the provenance trace
never claims otherwise; real containment (env-scrub) is a future concern,
NOT this scan — never market this scan as egress protection.

Path discipline: partner_config/partner_preflight live in harness/scripts and
resolve_actor in harness/hooks; both are added to sys.path off __file__
(never CWD), since this module is imported from an installed .claude/ tree
too (mirrors gemini_companion.py).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_none

_HERE = Path(__file__).resolve()
_HARNESS = _HERE.parents[3]                     # scripts→hs→plugins→harness
for _p in (_HARNESS / "scripts", _HARNESS / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gemini_secret_scrub as _scrub  # noqa: E402
import partner_config as _cfgmod  # noqa: E402
import partner_preflight as _preflight  # noqa: E402
from partner_core import (Degraded, Inert, JobRegistry, Result, _git_out,  # noqa: E402
                          _is_transient, _new_job_id, _now_iso, resolve_actor)
from partner_transport import CcsPrintTransport, PartnerError, PartnerTimeout  # noqa: E402

# Honesty stamp (step 4 HONESTY note above) — the scan is prompt-level only.
_EGRESS_SCOPE = "whole-repo-readable"

_TEMPLATES_PATH = _HARNESS / "plugins" / "hs" / "data" / "partner-prompt-templates.yaml"
_templates_cache = None


def _load_templates():
    """Load the per-purpose prompt templates (fail-open: a missing/broken
    file means the call runs with no preamble, never a crash). Mirrors
    gemini_companion._load_templates."""
    global _templates_cache
    if _templates_cache is None:
        try:
            import yaml_io
            _templates_cache = yaml_io.safe_load(
                _TEMPLATES_PATH.read_text(encoding="utf-8")) or {}
        except Exception as e:
            sys.stderr.write(
                "partner: WARNING — prompt templates unreadable at %s (%s); "
                "running with no methodology preamble\n" % (_TEMPLATES_PATH, e))
            _templates_cache = {}
    return _templates_cache


def _compose_prompt(purpose, prompt):
    """Prepend the purpose's role + methodology + shared output contract, so
    every path through the chokepoint hands the delegated provider the same
    rigor Claude's own advisory agents run by. No template for the purpose
    -> the raw prompt is used (mirrors gemini_companion._compose_prompt)."""
    t = _load_templates()
    block = (t.get("purposes") or {}).get(purpose)
    if not block:
        return prompt
    parts = [p for p in ((block.get("preamble") or "").rstrip(),
                         (t.get("output_contract") or "").rstrip()) if p]
    parts.append("--- TASK ---\n" + prompt)
    return "\n\n".join(parts)


def partner_call(purpose, prompt, provider, *, mode="plan", cwd=None, cfg=None,
                 config_path=None):
    """Route one advisory request to a ccs provider through the chokepoint —
    the ONE place policy-check/provider-validate/compose/scan/stamp/cost/
    degrade live (single chokepoint by construction — see
    test_partner_single_chokepoint.py).

    `cfg` lets a caller pass an already-resolved effective config (tests,
    the write path) instead of re-resolving from `config_path`.

    Returns Result | Inert | Degraded — never raises for an expected failure
    (a down ccs is a stamped Degraded, not an exception).
    """
    if cfg is None:
        cfg = _cfgmod.effective(_cfgmod.resolve(config_path))
    actor = resolve_actor()
    ts = _now_iso()

    # Step 1 — master=off ⇒ inert, DO NOT spawn.
    if cfg["master"] == "off":
        return Inert(
            reason="partner lane master=off — inert",
            provenance={"reviewer_engine": None, "reviewer_model": None,
                        "provider": provider, "purpose": purpose, "mode": mode,
                        "ts": ts, "actor": actor, "egress_scope": _EGRESS_SCOPE})

    # Step 1.5 — the ccs binary itself must resolve BEFORE ever spawning.
    # Checked here (not left to the transport) so a missing ccs is a stamped
    # Degraded — never a raised exception reaching the chokepoint's caller.
    if not _preflight.ccs_available():
        sys.stderr.write(
            "partner: refused — ccs not installed/resolvable on PATH (see "
            "your team's ccs setup doc; never auto-installed here)\n")
        return Degraded(
            reason="ccs not installed",
            provenance={"reviewer_engine": None, "reviewer_model": None,
                        "provider": provider, "purpose": purpose, "mode": mode,
                        "ts": ts, "actor": actor, "egress_scope": _EGRESS_SCOPE})

    # Step 2 — provider must be in LIVE discovery BEFORE ever spawning (never
    # call ccs with an unvalidated name).
    if not _preflight.validate_provider(provider):
        sys.stderr.write(
            "partner: refused — provider unknown: %s (run "
            "`partner_preflight.py --check` to see the live discovery list)\n"
            % provider)
        return Degraded(
            reason="provider unknown: %s" % provider,
            provenance={"reviewer_engine": None, "reviewer_model": None,
                        "provider": provider, "purpose": purpose, "mode": mode,
                        "ts": ts, "actor": actor, "egress_scope": _EGRESS_SCOPE})

    # Step 3 — compose FIRST so the scan (step 4) covers what actually egresses.
    composed = _compose_prompt(purpose, prompt)

    # Step 4 — secret-scan the COMPOSED payload, warn-only (see HONESTY above).
    hits = _scrub.scan(composed)
    if hits:
        where = ", ".join("%s@%d" % (h.pattern, h.offset) for h in hits)
        sys.stderr.write(
            "partner: WARNING — prompt may contain secret(s): %s (v1 "
            "warn-only, NOT blocked/redacted; prompt-level scan only — the "
            "delegated ccs provider can still Read+egress files off disk, "
            "see egress_scope)\n" % where)

    retry = cfg.get("retry") or {}
    attempts_allowed = max(1, int(retry.get("max_attempts", 1)))
    markers = [str(m).lower() for m in (retry.get("on_markers") or [])]
    timeout = _cfgmod.timeout_for(cfg, purpose)
    warn_at = cfg.get("cost_warn_usd")

    # Step 5 — spawn, retry on transient markers. NO cross-engine fallback:
    # a single lane by construction (this is the ONLY CcsPrintTransport()
    # construction site — see test_partner_single_chokepoint.py).
    transport = CcsPrintTransport()
    attempts_made = [0]  # closure cell: `before` fires unconditionally on every
    # attempt (success, non-transient failure, or exhaustion alike) — `after`
    # does NOT: tenacity skips it whenever the retry predicate says "don't
    # retry" (a successful attempt or a non-transient failure), which would
    # silently under-count exactly the two cases that matter most here.

    def _attempt():
        return transport.run(composed=composed, mode=mode, session=None,
                             cwd=cwd, timeout=timeout, provider=provider)

    def _transient(exc):
        return isinstance(exc, (PartnerError, PartnerTimeout)) and _is_transient(exc, markers)

    def _track_attempt(retry_state):
        attempts_made[0] = retry_state.attempt_number

    def _before_sleep(retry_state):
        # A failed write attempt can have left partial files in `cwd` (the
        # staging worktree, see _run_staged_write) — wipe them before the
        # retry so the final worktree diff never folds in attempt N's
        # garbage alongside the attempt that actually succeeds. Advisory
        # (plan-mode) calls never write, so they never take this branch.
        if mode == "write" and cwd:
            subprocess.run(["git", "-C", cwd, "reset", "--hard"],
                           capture_output=True, text=True)
            subprocess.run(["git", "-C", cwd, "clean", "-fd"],
                           capture_output=True, text=True)

    try:
        # wait_none() + sleep=noop: the original loop never backed off between
        # attempts (no time.sleep call at all) — the explicit no-op `sleep=`
        # avoids even wait_none()'s own zero-duration time.sleep(0.0) call, so
        # the retry stays a true immediate-continue like the hand-written
        # version. before_sleep still fires (it runs before `sleep()`, not
        # inside it) — that is what drives the git reset/clean cleanup below.
        rr = Retrying(
            stop=stop_after_attempt(attempts_allowed),
            wait=wait_none(),
            sleep=lambda _seconds: None,
            retry=retry_if_exception(_transient),
            before=_track_attempt,
            before_sleep=_before_sleep,
            reraise=True,
        )(_attempt)
    except (PartnerError, PartnerTimeout) as e:
        # Step 8 — transport exhausted -> Degraded LOUD + stamped, never a
        # silent main-Claude fallback.
        stamp = {"reviewer_engine": "ccs:" + provider, "reviewer_model": None,
                 "provider": provider, "purpose": purpose, "mode": mode,
                 "ts": ts, "actor": actor, "attempts": attempts_made[0],
                 "egress_scope": _EGRESS_SCOPE}
        sys.stderr.write(
            "partner: DEGRADED — ccs:%s failed (%s); NO silent Claude fallback\n"
            % (provider, e))
        return Degraded(provenance=stamp, reason=str(e))

    content = rr.content or {}
    cost = content.get("cost")
    # Step 6 — stamp provenance: `ccs:`-prefixed engine, model+cost from the
    # JSON record (never self-computed).
    stamp = {"reviewer_engine": "ccs:" + provider,
             "reviewer_model": content.get("model"), "provider": provider,
             "purpose": purpose, "mode": mode, "cost": cost, "ts": ts,
             "actor": actor, "attempts": attempts_made[0],
             "egress_scope": _EGRESS_SCOPE}
    # Step 7 — cost over the warn threshold: warn stderr + stamp.
    over = (isinstance(cost, (int, float)) and isinstance(warn_at, (int, float))
            and cost > warn_at)
    stamp["cost_over"] = bool(over)
    if over:
        sys.stderr.write(
            "partner: WARNING — cost $%.4f exceeded cost_warn_usd $%.4f "
            "(provider=%s, purpose=%s)\n" % (cost, warn_at, provider, purpose))
    return Result(content=content, provenance=stamp, session=rr.session)


# --- job orchestration (registry itself lives in partner_core) --------------
_VERB_PURPOSE = {
    "review": "review",
    "adversarial-review": "redteam",
    "research": "research",
    "critique": "critique",
}
_TERMINAL = {"ok": "done", "degraded": "degraded", "inert": "inert"}

# `task` (delegated coding) is not an advisory verb, so it carries no
# purpose->methodology mapping of its own — this is the default purpose
# stamped when the caller does not override it. It is deliberately NOT one
# of partner_config.ADVISORY_PURPOSES, so a plain `task` call is free to
# write; only an explicit `--purpose` override into one of the 4 advisory
# names is refused when write/live is requested.
_TASK_DEFAULT_PURPOSE = "task"


def _run_job(reg, verb, purpose, prompt, provider, mode, config_path=None):
    """Run one job synchronously through the chokepoint, logging
    running->terminal (append-only — resolve_actor/ts auto-filled by
    JobRegistry.append). `config_path` plumbs the CLI's --config through to
    partner_call (defaults to the shipped/env-resolved policy, same as a
    direct partner_call(config_path=None) caller).

    partner_call always returns Result|Inert|Degraded for an EXPECTED failure
    (a down ccs, an unknown provider, ...) — the terminal append below covers
    that. The try/except here is the backstop for an UNEXPECTED exception (a
    real bug in the chokepoint): it still appends a terminal "failed" record
    before re-raising, so a job can never be stranded at "running"."""
    job_id = _new_job_id()
    reg.append({"job_id": job_id, "verb": verb, "purpose": purpose,
                "provider": provider, "status": "running", "mode": mode})
    try:
        out = partner_call(purpose, prompt, provider, mode=mode, config_path=config_path)
    except Exception as e:
        reg.append({"job_id": job_id, "verb": verb, "purpose": purpose,
                    "provider": provider, "status": "failed", "mode": mode,
                    "reason": str(e)})
        raise
    reg.append({"job_id": job_id, "verb": verb, "purpose": purpose,
                "provider": provider, "status": _TERMINAL.get(out.status, out.status),
                "mode": mode, "cost": out.provenance.get("cost"),
                "model": out.provenance.get("reviewer_model"),
                "provenance": out.provenance, "result": getattr(out, "content", None),
                "reason": getattr(out, "reason", None)})
    return job_id, out


def _run_staged_write(provider, prompt, purpose, cfg, *, repo_root=None,
                      apply_live=False):
    """Stage a delegated coding task's edits in a throwaway git worktree,
    return the diff, and leave the LIVE tree untouched by default (mirrors
    gemini_companion._run_sandbox_write, reusing the shared
    partner_core._git_out plumbing rather than reimplementing git).

    HONESTY: a git worktree is a JAIL, NOT an OS sandbox — ccs's own tools
    can still write anywhere the invoking process can reach; nothing here
    PREVENTS that. The worktree carries no `.claude/settings.json`, so a
    `ccs -p` turn running inside it does not run this repo's guard hooks
    either. Containment here is the AFTER-diff gate (empty-diff raise +
    escape-scan against the pre-call baseline) — never an in-worktree hook.

    `apply_live` (only ever True under the caller's allow_live gate) applies
    the exact captured diff to `repo_root` via `git apply` — a controlled
    blast radius, deliberately never turning ccs's accept-edits tools loose
    on repo_root directly (that would let it write ANYWHERE in cwd, not just
    the delegated task).

    Returns Result(content={"diff", "escaped"}, provenance) with
    provenance["mode"] stamped "live" or "write" (staged). Raises
    PartnerError on an empty diff or a write turn that did not complete
    (never a silent "done"); the worktree is removed on every exit path.
    """
    if repo_root is None:
        repo_root = _git_out(os.getcwd(), "rev-parse", "--show-toplevel").strip()

    reg = JobRegistry(subdir="partner")
    wt_base = reg._dir / "worktrees"
    wt_base.mkdir(parents=True, exist_ok=True)
    wt = wt_base / _new_job_id()
    baseline = _git_out(repo_root, "status", "--porcelain")
    created = False
    try:
        subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                        str(wt), "HEAD"], check=True, capture_output=True, text=True)
        created = True
        # THE engine interaction goes through the single chokepoint —
        # provider-validate, secret-scan, template, provenance stamp, retry,
        # degrade all happen once there. mode="write" drops the
        # advisory --permission-mode flag (partner_transport
        # ._ADVISORY_MODES) so ccs actually writes.
        out = partner_call(purpose, prompt, provider, mode="write", cwd=str(wt),
                           cfg=cfg)
        if getattr(out, "status", None) != "ok":
            # A write that did not run must fail LOUDLY, never report "done".
            raise PartnerError("staged write did not complete: %s"
                               % getattr(out, "reason", out.status))
        subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True,
                       capture_output=True, text=True)
        diff = _git_out(wt, "diff", "--cached")
        # An empty diff means ccs wrote NOTHING applicable to the worktree —
        # refuse to report "done" on a no-op write; raise so the caller
        # records a stamped `failed` rather than a silent success.
        if not diff.strip():
            raise PartnerError(
                "staged write produced an EMPTY diff — ccs wrote nothing to "
                "the worktree; refusing to report done on a no-op")
        escaped = _git_out(repo_root, "status", "--porcelain") != baseline
        if escaped:
            sys.stderr.write(
                "partner: ESCAPE WARNING — the live tree changed during a "
                "staged write (ccs wrote outside its worktree); job flagged "
                "escaped, DIFF IS INCOMPLETE\n")
            if apply_live:
                # The captured diff cannot be trusted as the FULL picture of
                # what ccs did — applying it to repo_root would silently
                # accept an incomplete change. Refuse rather than apply.
                raise PartnerError(
                    "staged write escaped its worktree (the live tree "
                    "changed during the call) — refusing to apply an "
                    "incomplete diff to the live tree")
        mode_stamp = "write"
        if apply_live:
            # Apply the exact reviewed diff to repo_root — controlled blast
            # radius, see the docstring's HONESTY note above.
            subprocess.run(["git", "-C", str(repo_root), "apply"], input=diff,
                           check=True, capture_output=True, text=True)
            mode_stamp = "live"
        prov = dict(out.provenance)
        prov["mode"] = mode_stamp
        return Result(content={"diff": diff, "escaped": escaped}, provenance=prov,
                     session=out.session)
    finally:
        if created:
            cleanup = subprocess.run(
                ["git", "-C", str(repo_root), "worktree", "remove", "--force",
                 str(wt)], capture_output=True, text=True)
            if cleanup.returncode != 0:
                # Best-effort cleanup — a leaked worktree directory is a
                # nuisance, not a correctness issue, so this warns rather
                # than raises. Silence would hide a real leak, though.
                sys.stderr.write(
                    "partner: WARNING — worktree cleanup failed for %s (%s)\n"
                    % (wt, (cleanup.stderr or "").strip()))


def main(argv=None) -> int:
    """Verb CLI. `partner_companion.py <verb> ...`:
        review | adversarial-review | research | critique  — run an advisory job
        task                                                — delegated coding job:
                                                                read-only proposal by
                                                                default; --write stages
                                                                a worktree diff; --live
                                                                additionally applies it
                                                                to the live tree, gated
                                                                by allow_live
        status <job_id> | result <job_id>                  — inspect a job
        preflight                                            — ccs discovery check
    """
    import argparse
    ap = argparse.ArgumentParser(description="ccs partner lane (advisory)")
    sub = ap.add_subparsers(dest="verb", required=True)

    for v in _VERB_PURPOSE:
        sp = sub.add_parser(v)
        sp.add_argument("-p", "--prompt", required=True)
        sp.add_argument("--provider", required=True,
                        help="ccs provider profile to delegate to (required — "
                             "never call ccs blind)")
        sp.add_argument("--config", default=None)
        sp.add_argument("--purpose", default=None,
                        help="override the default purpose->methodology mapping")

    task_sp = sub.add_parser("task")
    task_sp.add_argument("-p", "--prompt", required=True)
    task_sp.add_argument("--provider", required=True,
                         help="ccs provider profile to delegate to (required — "
                              "never call ccs blind)")
    task_sp.add_argument("--config", default=None)
    task_sp.add_argument("--purpose", default=None,
                         help="override the default coding-task purpose "
                              "(passing one of the 4 advisory purposes here "
                              "with --write/--live is refused)")
    task_sp.add_argument("--write", action="store_true",
                         help="stage the delegated edit in a throwaway "
                              "worktree and return the diff — the live tree "
                              "is NOT touched")
    task_sp.add_argument("--live", action="store_true",
                         help="INTENT marker: additionally apply the staged "
                              "diff to the live tree. NOT a second security "
                              "layer — the real gate is allow_live in "
                              "partner.yaml (env-restart bound); --live "
                              "alone can never cross it")
    task_sp.add_argument("--background", action="store_true",
                         help="does NOT detach the process — this is a guard "
                              "flag only: forbidden together with --write/"
                              "--live (a detached worker could not gate its "
                              "own worktree diff), a no-op alongside a plain "
                              "read-only task")

    for v in ("status", "result"):
        sub.add_parser(v).add_argument("job_id")

    sub.add_parser("preflight")

    args = ap.parse_args(argv)

    if args.verb in _VERB_PURPOSE:
        purpose = args.purpose or _VERB_PURPOSE[args.verb]
        reg = JobRegistry(subdir="partner")
        job_id, out = _run_job(reg, args.verb, purpose, args.prompt, args.provider,
                               "plan", config_path=args.config)
        print(json.dumps({"job_id": job_id, "status": reg.latest(job_id)["status"],
                          "provenance": out.provenance,
                          "result": getattr(out, "content", None),
                          "cost": out.provenance.get("cost")}, ensure_ascii=False))
        return 0 if out.status in ("ok", "inert") else 3

    if args.verb == "task":
        purpose = args.purpose or _TASK_DEFAULT_PURPOSE
        write_flag, live_flag, background = args.write, args.live, args.background
        want_write = write_flag or live_flag

        # Advisory purposes only ever read+report — never write, live or
        # not, even if the caller overrides --purpose to one of the 4
        # advisory names.
        if want_write and _cfgmod.is_advisory(purpose):
            sys.stderr.write(
                "partner: refused — advisory purpose %r cannot use the "
                "write/live path (advisory purposes never write)\n" % purpose)
            return 2

        # A detached worker cannot gate its own worktree diff.
        if background and want_write:
            sys.stderr.write(
                "partner: refused — background + write/live is forbidden: a "
                "detached worker cannot gate its own worktree diff\n")
            return 2

        cfg = _cfgmod.effective(_cfgmod.resolve(args.config))

        # The ONE real mechanical gate for --live (env-restart bound):
        # --live is an INTENT marker the caller self-passes under a standing
        # grant already encoded by allow_live:on — it can never cross the
        # gate by itself.
        if live_flag and not _cfgmod.allow_live(cfg):
            sys.stderr.write(
                "partner: refused — --live requires allow_live: on in "
                "partner.yaml plus a harness restart (the real gate; --live "
                "alone never crosses it)\n")
            return 2

        if want_write and cfg["write"] != "worktree_staged":
            sys.stderr.write(
                "partner: refused — write/live requested but lane write=%s "
                "(set write: worktree_staged to enable the staging path)\n"
                % cfg["write"])
            return 2

        reg = JobRegistry(subdir="partner")

        if not want_write:
            # Default: a read-only proposal, no tree touched.
            job_id, out = _run_job(reg, "task", purpose, args.prompt, args.provider,
                                   "plan", config_path=args.config)
            print(json.dumps({"job_id": job_id, "status": reg.latest(job_id)["status"],
                              "provenance": out.provenance,
                              "result": getattr(out, "content", None)},
                             ensure_ascii=False))
            return 0 if out.status in ("ok", "inert") else 3

        job_id = _new_job_id()
        mode_stamp = "live" if live_flag else "write"
        reg.append({"job_id": job_id, "verb": "task", "purpose": purpose,
                    "provider": args.provider, "status": "running", "mode": mode_stamp})
        try:
            out = _run_staged_write(args.provider, args.prompt, purpose, cfg,
                                    apply_live=live_flag)
        except (PartnerError, PartnerTimeout, OSError,
                subprocess.CalledProcessError) as e:
            reg.append({"job_id": job_id, "verb": "task", "purpose": purpose,
                        "provider": args.provider, "status": "failed",
                        "mode": mode_stamp, "reason": str(e)})
            sys.stderr.write("partner: staged write failed (%s)\n" % e)
            return 3
        reg.append({"job_id": job_id, "verb": "task", "purpose": purpose,
                    "provider": args.provider, "status": "done",
                    "mode": out.provenance.get("mode"), "provenance": out.provenance,
                    "result": out.content, "cost": out.provenance.get("cost")})
        print(json.dumps({"job_id": job_id, "status": "done",
                          "provenance": out.provenance,
                          "diff": out.content.get("diff"),
                          "escaped": out.content.get("escaped")}, ensure_ascii=False))
        return 0

    if args.verb in ("status", "result"):
        reg = JobRegistry(subdir="partner")
        rec = reg.latest(args.job_id)
        if rec is None:
            sys.stderr.write("partner: no such job %s\n" % args.job_id)
            return 2
        if args.verb == "status":
            print(json.dumps({"job_id": args.job_id, "status": rec["status"]},
                             ensure_ascii=False))
        else:
            print(json.dumps({"job_id": args.job_id, "result": rec.get("result"),
                              "provenance": rec.get("provenance")}, ensure_ascii=False))
        return 0

    if args.verb == "preflight":
        return _preflight.main(["--check"])

    return 2


if __name__ == "__main__":
    sys.exit(main())
