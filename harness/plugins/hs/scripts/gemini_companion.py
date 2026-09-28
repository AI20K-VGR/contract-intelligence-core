#!/usr/bin/env python3
"""gemini_companion.py — the ONE chokepoint every gemini call passes through.

`partner_call(purpose, prompt, ...)` is the single place that (1) reads the lane
config, (2) refuses when master=off (inert, no spawn), (3) resolves the model for
the purpose (override wins, else the purpose tier — never a hardcoded id, RT-12),
(4) WARNS on secrets in the prompt (D7 v1: warn-only, never mask/block), (5)
stamps provenance (engine+model) on every outcome (D6), (6) drives the ACP client,
and (7) degrades LOUDLY + stamped on a down gemini — NEVER a silent Claude
fallback (S4/RT-07). Verbs (P4) and the worktree-staging write path (P5) append to
this module; keeping one chokepoint is what makes the P8 drift-test meaningful.

Path discipline: the config loader lives in harness/scripts and resolve_actor in
harness/hooks; both are added to sys.path off __file__ (never CWD), since this
module is imported from an installed .claude/ tree too.
"""
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_HARNESS = _HERE.parents[3]                     # scripts→hs→plugins→harness
for _p in (_HARNESS / "scripts", _HARNESS / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_none

import gemini_partner_config as _cfgmod  # noqa: E402
import gemini_secret_scrub as _scrub  # noqa: E402
import resolve_model as _rm  # noqa: E402
from gemini_transport import (AcpError, AcpTimeout, GeminiPrintTransport,  # noqa: E402
                              PrintTransport)
# Provider-agnostic primitives live in partner_core (shared with a future
# partner lane); re-exported here so every existing `gc.<symbol>` call site
# keeps resolving unchanged (back-compat shim, not a new surface).
from partner_core import (Degraded, Inert, JobRegistry, Result, _git_out,  # noqa: E402
                          _is_transient, _new_job_id, _now_iso, resolve_actor)


# The engine domain is CLOSED (D11: never Claude). Cross-engine fallback only ever
# hops between these two — the map IS the guarantee no third lane can appear.
_OTHER_ENGINE = {"gemini-print": "agy-print", "agy-print": "gemini-print"}

# The sandbox write-target marker: _run_sandbox_write injects this + the worktree
# absolute path into the write prompt so agy (which ignores cwd) lands files in the
# jail. Kept in sync with the fake's _WRITE_DIR_RE.
_SANDBOX_WRITE_MARKER = "[sandbox-write-dir]"


def _model_for(cfg, purpose) -> str:
    """Override wins (already S7-validated ∈ available at load), else the purpose
    tier resolved through the model SSOT."""
    override = (cfg.get("overrides") or {}).get(purpose)
    if override:
        return override
    return _cfgmod.tier_for(cfg, purpose)


_TEMPLATES_PATH = _HARNESS / "plugins" / "hs" / "data" / "gemini-prompt-templates.yaml"
_templates_cache = None


def _load_templates():
    """Load the per-purpose prompt templates (fail-open: a missing/broken file
    means the call runs with no preamble, never a crash). Companion-owned data so
    it survives the skill being stashed OFF."""
    global _templates_cache
    if _templates_cache is None:
        try:
            import yaml_io
            _templates_cache = yaml_io.safe_load(
                _TEMPLATES_PATH.read_text(encoding="utf-8")) or {}
        except Exception as e:
            # Fail-open (templates are a quality boost, not a safety gate — a bad
            # file must not break the lane), but WARN so a broken/missing templates
            # file is visible, never silently swallowed (dogfood finding).
            sys.stderr.write("gemini-partner: WARNING — prompt templates unreadable "
                             "at %s (%s); running with no methodology preamble\n"
                             % (_TEMPLATES_PATH, e))
            _templates_cache = {}
    return _templates_cache


def _compose_prompt(purpose, prompt):
    """Prepend the purpose's role + methodology + shared output contract, so every
    path through the chokepoint gives gemini the same rigor Claude's own advisory
    agents run by. No template for the purpose → the raw prompt is used."""
    t = _load_templates()
    block = (t.get("purposes") or {}).get(purpose)
    if not block:
        return prompt
    parts = [p for p in ((block.get("preamble") or "").rstrip(),
                         (t.get("output_contract") or "").rstrip()) if p]
    parts.append("--- TASK ---\n" + prompt)
    return "\n\n".join(parts)


def _output_contract_text() -> str:
    """The shared output contract, standalone. Appended UNCONDITIONALLY on the
    --skill path (F-E): a skill's methodology REPLACES the purpose preamble, but
    the output shape must never drop."""
    return (_load_templates().get("output_contract") or "").rstrip()


# Seams for the --skill path: default None lets gemini_skill_inject resolve the
# live skill/rules trees off __file__; tests override to a fixture tree.
def _skill_skills_dir():
    return None


def _skill_harness_root():
    return None


def _compose_skill_prompt(purpose, prompt, skill_name):
    """Compose the --skill payload: SKILL.md + cited rules/references VERBATIM
    (mechanical resolve, no LLM), then the output_contract ALWAYS (F-E), then the
    user task. `purpose` only shapes the stamp — the skill methodology stands in
    for any purpose preamble."""
    import gemini_skill_inject as _gsi
    composed_skill, _refs = _gsi.resolve_skill(
        skill_name, skills_dir=_skill_skills_dir(),
        harness_root=_skill_harness_root())
    parts = [composed_skill.rstrip()]
    oc = _output_contract_text()
    if oc:
        parts.append(oc)
    parts.append("--- TASK ---\n" + prompt)
    return "\n\n".join(parts)


def partner_call(purpose, prompt, *, session=None, mode="plan", cwd=None,
                 config_path=None, cfg=None, skill=None, engine=None):
    """Route one advisory/coding request to gemini through the chokepoint — the
    ONE place model-resolve, secret-scan, provenance-stamp, retry, and degrade
    live. Both the advisory read path AND the sandbox-write path go through here
    (RT-05 single chokepoint by construction).

    `mode="plan"` (default) is the read-only surface; `mode="yolo"` enables edits
    (set_mode issued here), used by the worktree-staging write path with `cwd` set
    to the worktree. `cfg` lets a caller pass an already-resolved effective config
    (the write path) instead of re-resolving from `config_path`.

    Returns Result | Inert | Degraded — never raises for an expected failure
    (a down gemini is a stamped Degraded, not an exception).
    """
    if cfg is None:
        cfg = _cfgmod.effective(_cfgmod.resolve(config_path))
    actor = resolve_actor()
    ts = _now_iso()

    if cfg["master"] == "off":
        return Inert(
            reason="gemini partner lane master=off — inert",
            provenance={"reviewer_engine": "gemini", "reviewer_model": None,
                        "purpose": purpose, "ts": ts, "actor": actor})

    # Compose FIRST so the secret-scan can cover the payload that actually
    # egresses. On the --skill path the SKILL.md + cited rules are inlined, so a
    # secret buried in an injected rule must be scanned too (F-B) — the old scan
    # of the raw prompt alone would miss it. The stamp is built PER engine below
    # (the winning engine's diagonal, F9), so injected_skill rides in stamp_extra.
    stamp_extra = {}
    if skill:
        composed = _compose_skill_prompt(purpose, prompt, skill)
        stamp_extra["injected_skill"] = skill
        scan_target = composed
    else:
        composed = _compose_prompt(purpose, prompt)
        scan_target = prompt  # no injection → the user content is the whole egress

    hits = _scrub.scan(scan_target)
    if hits:
        where = ", ".join("%s@%d" % (h.pattern, h.offset) for h in hits)
        sys.stderr.write(
            "gemini-partner: WARNING — prompt may contain secret(s): %s "
            "(v1 warn-only, NOT blocked/redacted — route-all sends this to Google)\n"
            % where)
    retry = cfg.get("retry") or {}
    attempts = max(1, int(retry.get("max_attempts", 1)))
    markers = [str(m).lower() for m in (retry.get("on_markers") or [])]
    timeout = _cfgmod.timeout_for(cfg, purpose)

    # Resolve the engine ORDER. A pinned engine (--engine arg, or a concrete config
    # axis) runs ALONE; `auto` adds the cross-engine fallback. Fallback is disabled
    # for the write path (mode∈{yolo,write}, D10) and mid-conversation (session set,
    # scenario-CRITICAL: a session-id belongs to ONE engine — never inject it into
    # the other). The order set is CLOSED to {gemini,agy} via _OTHER_ENGINE (D11).
    axis = engine if engine is not None else cfg.get("engine", "auto")
    if axis == "auto":
        primary = _cfgmod._resolve_engine(cfg)
        fallback_ok = True
    else:
        primary = axis
        fallback_ok = False
    if mode in ("yolo", "write") or session is not None:
        fallback_ok = False
    order = [primary]
    if fallback_ok:
        order.append(_OTHER_ENGINE[primary])

    def _diag(eng):
        """(engine, transport, auth, model) for an engine — the D32 diagonal. agy
        reads its model from _agy_model_for; gemini keeps _model_for untouched. Both
        engines now drive print transport (ACP retired)."""
        if eng == "agy-print":
            return "agy", "print", "oauth", _cfgmod._agy_model_for(cfg, purpose)
        return "gemini", "print", "apikey", _model_for(cfg, purpose)

    # D25: engine=auto but NO credential (no GEMINI_API_KEY, no agy login) — short-
    # circuit to a stamped inert-auth rather than spawning two engines that both
    # fail. STILL name how to enable the lane (scenario-HIGH: never a silent abort).
    # Gate on the EFFECTIVE axis (review M-1): an arg-level `--engine` pin means the
    # caller chose a lane — attempt it (and let it fail on its own missing cred),
    # never short-circuit a pinned call with an "engine=auto" diagnostic.
    if axis == "auto" and _cfgmod._auth_inert(cfg):
        d_engine, d_transport, d_auth, d_model = _diag(primary)
        sys.stderr.write(
            "gemini-partner: INERT-AUTH — engine=auto but no credential (no "
            "GEMINI_API_KEY, no agy login). Run `agy` to log in (agy-print) or set "
            "GEMINI_API_KEY (gemini-print); NO silent Claude fallback\n")
        return Degraded(
            provenance={"reviewer_engine": d_engine, "reviewer_model": d_model,
                        "engine": d_engine, "transport": d_transport, "auth": d_auth,
                        "purpose": purpose, "mode": mode, "ts": ts, "actor": actor,
                        "attempts": []},
            reason="inert-auth: no engine credential (auto with neither GEMINI_API_KEY "
                   "nor agy login)")

    # Both engines are write citizens now: gemini writes cwd via `--approval-mode yolo`;
    # agy writes a prompt-delivered ABSOLUTE path (it ignores cwd) with SSH_* stripped
    # (the transport handles both). The worktree jail + escape-scan + empty-diff guard
    # bound the blast — no engine is refused the write path (the old S5-style agy refusal
    # is retired on the empirical write re-probe).

    # The engine lifecycle lives behind the transport seam; partner_call keeps the
    # retry/fallback/degrade shell so ONE chokepoint owns model-resolve/scan/stamp.
    # attempts_log records every engine tried (D12); the winner's stamp carries its
    # OWN diagonal + the full trail (F9). Both engines are print transports — gemini
    # via HARNESS_GEMINI_PRINT_CMD, agy via HARNESS_AGY_CMD (the fake seams).
    attempts_log = []
    last_err = None
    for eng in order:
        e_engine, e_transport, e_auth, e_model = _diag(eng)
        if eng == "agy-print":
            transport = PrintTransport()
        else:
            transport = GeminiPrintTransport()

        def _attempt(transport=transport, e_model=e_model):
            return transport.run(composed=composed, mode=mode, session=session,
                                 cwd=cwd, timeout=timeout, model=e_model,
                                 engine_cfg=cfg)

        def _transient(exc):
            # Only the three types the hand-written loop caught are ever retried
            # or recorded below — anything else propagates uncaught, unchanged.
            return isinstance(exc, (AcpTimeout, AcpError, OSError)) and _is_transient(exc, markers)

        try:
            # wait_none() + sleep=noop: the original loop never backed off between
            # attempts (no time.sleep call at all) — only stop_after_attempt(attempts)
            # + the transient predicate governed whether a retry happened,
            # immediately. The explicit no-op `sleep=` avoids even wait_none()'s own
            # zero-duration time.sleep(0.0) call, so the retry stays a true
            # immediate-continue like the hand-written version.
            rr = Retrying(
                stop=stop_after_attempt(attempts),
                wait=wait_none(),
                sleep=lambda _seconds: None,
                retry=retry_if_exception(_transient),
                reraise=True,
            )(_attempt)
        except (AcpTimeout, AcpError, OSError) as e:
            # OSError covers a missing binary (Popen) — a down peer, not a
            # crash: degrade loudly, never a silent Claude fallback (S4).
            last_err = e
            attempts_log.append({"engine": e_engine, "transport": e_transport,
                                 "auth": e_auth, "model": e_model, "status": "failed",
                                 "reason": str(e)})
            continue

        attempts_log.append({"engine": e_engine, "transport": e_transport,
                             "auth": e_auth, "model": e_model, "status": "ok"})
        stamp = {"reviewer_engine": e_engine, "reviewer_model": e_model,
                 "engine": e_engine, "transport": e_transport, "auth": e_auth,
                 "purpose": purpose, "mode": mode, "ts": ts, "actor": actor,
                 "attempts": attempts_log, **stamp_extra}
        return Result(content=rr.content, provenance=stamp, session=rr.session)

    # Every engine in the order exhausted → degrade LOUD, stamped with the primary
    # diagonal + the full attempts trail (never a silent Claude fallback, S4/D11).
    d_engine, d_transport, d_auth, d_model = _diag(primary)
    stamp = {"reviewer_engine": d_engine, "reviewer_model": d_model,
             "engine": d_engine, "transport": d_transport, "auth": d_auth,
             "purpose": purpose, "mode": mode, "ts": ts, "actor": actor,
             "attempts": attempts_log, **stamp_extra}
    sys.stderr.write(
        "gemini-partner: DEGRADED — all engines failed (%s); tried %s; NO silent "
        "Claude fallback\n" % (last_err, [a["engine"] for a in attempts_log]))
    return Degraded(provenance=stamp, reason=str(last_err))


# --- job orchestration (gemini-shape; JobRegistry itself lives in partner_core) --
import json  # noqa: E402

# verb → purpose default; write verbs are delegated (mode resolved from config).
_VERB_PURPOSE = {
    "review": "review",
    "adversarial-review": "redteam",
    "research": "research",
    "task": "delegate",
}
# status word emitted per outcome kind.
_TERMINAL = {"ok": "done", "degraded": "degraded", "inert": "inert"}


def _stats_of(out) -> dict:
    """Token stats from a result, normalized across the three shapes the lane sees:
    gemini -p -o json nests them at stats.models.<model>.tokens (print, current);
    ACP puts them at result._meta.quota.token_count (retired at P6); a flat `stats`
    is legacy/fake. Fail-open {} on any unknown/partial shape — never crash."""
    content = getattr(out, "content", None)
    if not isinstance(content, dict):
        return {}
    stats = content.get("stats")
    if isinstance(stats, dict):
        models = stats.get("models")
        if isinstance(models, dict):
            # print shape: sum token usage across every model in the call so a
            # multi-model turn drops nothing; a models blob with no tokens → {}.
            agg = {"input_tokens": 0, "total_tokens": 0, "thoughts_tokens": 0}
            found = False
            for m in models.values():
                tok = m.get("tokens") if isinstance(m, dict) else None
                if not isinstance(tok, dict):
                    continue
                found = True
                # `or 0` (not a get default): an EXPLICIT null in the wire payload
                # keeps the key, so get(k, 0) returns None → int += None crashes.
                agg["input_tokens"] += tok.get("input") or 0
                agg["total_tokens"] += tok.get("total") or 0
                agg["thoughts_tokens"] += tok.get("thoughts") or 0
            return agg if found else {}
        return stats  # legacy flat stats (back-compat to P6)
    tc = (((content.get("_meta") or {}).get("quota") or {}).get("token_count"))
    if isinstance(tc, dict):  # guard: a scalar token_count from wire drift must not crash
        return {"input_tokens": tc.get("input_tokens", 0),
                "output_tokens": tc.get("output_tokens", 0)}
    return {}


def _run_job(reg, verb, purpose, prompt, mode, config_path, skill=None, round_n=None,
             engine=None):
    """Run one job synchronously through the chokepoint, logging running→attempts→
    terminal (all APPENDED — the append-only lifecycle status verbs read). `round_n`
    stamps the Claude-driven loop iteration on the records (append-only, never
    rewritten); it is absent for a plain one-shot call. `engine` pins the transport
    (disables cross-engine fallback)."""
    job_id = _new_job_id()
    extra = {}
    if skill:
        extra["injected_skill"] = skill
    if round_n is not None:
        extra["round_n"] = round_n
    reg.append({"job_id": job_id, "verb": verb, "purpose": purpose,
                "status": "running", "mode": mode, **extra})
    out = partner_call(purpose, prompt, mode=mode, config_path=config_path,
                       skill=skill, engine=engine)
    # D12: one append-only record per engine attempt (the winner + each failed
    # fallback), so the registry shows the full cross-engine trail without ever
    # rewriting a line.
    for att in (out.provenance.get("attempts") or []):
        reg.append({"job_id": job_id, "verb": verb, "purpose": purpose,
                    "status": "attempt", "engine": att.get("engine"),
                    "transport": att.get("transport"),
                    "attempt_status": att.get("status"),
                    "reason": att.get("reason"), "model": att.get("model"), **extra})
    reg.append({"job_id": job_id, "verb": verb, "purpose": purpose,
                "status": _TERMINAL.get(out.status, out.status),
                "mode": mode, "model": out.provenance.get("reviewer_model"),
                "provenance": out.provenance, "result": getattr(out, "content", None),
                "reason": getattr(out, "reason", None), "stats": _stats_of(out),
                "session": getattr(out, "session", None), **extra})
    return job_id, out


def _run_sandbox_write(reg, job_id, purpose, prompt, cfg, repo_root=None, engine=None):
    """Stage gemini's edits in a throwaway git worktree, return the diff, leave
    the ROOT working tree untouched (RT-01). The escape-scan detects an IN-REPO
    escape only (git status of repo_root) — with full-env-inherit + yolo, gemini's
    tools can still write outside the repo (~/.ssh, /tmp, a sibling repo); nothing
    here PREVENTS that (F3: NOT an OS sandbox, v2). A set_mode or prompt failure
    RAISES (never a silent "done", RT-U1); the worktree is removed in every exit
    path.

    Returns Result(content={"diff", "escaped"}, provenance). Claude applies the
    diff — the companion never touches the live tree itself.
    """
    if repo_root is None:
        repo_root = _git_out(os.getcwd(), "rev-parse", "--show-toplevel").strip()

    wt_base = reg._dir / "worktrees"
    wt_base.mkdir(parents=True, exist_ok=True)
    wt = wt_base / job_id
    baseline = _git_out(repo_root, "status", "--porcelain")
    created = False
    try:
        subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "--detach",
                        str(wt), "HEAD"], check=True, capture_output=True, text=True)
        created = True
        # Deliver the worktree as an ABSOLUTE write-target in the prompt: agy ignores
        # cwd (writes its own scratch by default), so an abspath in the prompt is the
        # only contract that lands the file in the jail. gemini (cwd-bound) tolerates
        # the redundant hint. The marker is what the fake + a real engine key on.
        wt_abspath = os.path.abspath(str(wt))
        write_prompt = ("%s\n\n%s %s\n(Write every file you create or edit under that "
                        "absolute directory.)" % (prompt, _SANDBOX_WRITE_MARKER,
                                                   wt_abspath))
        # THE engine interaction goes through the single chokepoint — model-resolve,
        # secret-scan, template, provenance stamp, retry, degrade all happen once
        # there. This path only adds the worktree + diff capture around it (RT-05).
        out = partner_call(purpose, write_prompt, mode="yolo", cwd=str(wt), cfg=cfg,
                           engine=engine)
        if getattr(out, "status", None) != "ok":
            # A write that did not run must fail LOUDLY, never report "done"
            # (RT-U1). partner_call already warned; surface it as an error the CLI
            # records as a stamped `failed`.
            raise AcpError("sandbox write did not complete: %s"
                           % getattr(out, "reason", out.status))
        subprocess.run(["git", "-C", str(wt), "add", "-A"],
                       check=True, capture_output=True, text=True)
        diff = _git_out(wt, "diff", "--cached")
        # F4: an empty worktree diff means the engine wrote NOTHING applicable here —
        # agy can land in its scratch OUTSIDE the repo, where the escape-scan (which
        # only diffs repo_root) is blind. Refuse to report "done" on a no-op write;
        # raise so the CLI records a stamped `failed`. Do NOT lean on `escaped`:
        # escaped=False with an empty diff IS the silent-success case this guard
        # catches. Known edge (backlogged): a write landing ONLY in a repo-.gitignored
        # path also yields an empty `diff --cached` (the worktree inherits .gitignore),
        # so it reads as failed — acceptable here since there is no applicable diff to
        # hand back for such a write; softening to `git status --ignored` is deferred.
        if not diff.strip():
            raise AcpError(
                "sandbox write produced an EMPTY diff — the engine wrote nothing to "
                "the worktree (agy may have written to its scratch OUTSIDE repo_root, "
                "which the escape-scan cannot see); refusing to report done on a no-op")
        escaped = _git_out(repo_root, "status", "--porcelain") != baseline
        if escaped:
            sys.stderr.write(
                "gemini-partner: ESCAPE WARNING — the live tree changed during a "
                "sandbox write (the engine wrote outside its worktree); job flagged "
                "escaped, DIFF IS INCOMPLETE\n")
        return Result(content={"diff": diff, "escaped": escaped},
                      provenance=out.provenance, session=out.session)
    finally:
        if created:
            subprocess.run(["git", "-C", str(repo_root), "worktree", "remove",
                            "--force", str(wt)], capture_output=True, text=True)


# --- setup: canary probe + orphan reap (final append, no phase after) -------
def _canary(cfg) -> dict:
    """Probe the live gemini print surface: one `gemini -p "ok" -o json` and confirm
    it answers + parses (there is no ACP handshake to check anymore — print self-exits).
    Never blocks (D12) — a down/keyless gemini returns a warning that names how to
    enable the lane. Uses the GeminiPrintTransport seam so the fake drives it in tests."""
    model = _model_for(cfg, "review")
    try:
        rr = GeminiPrintTransport().run(composed="ok", mode="plan", session=None,
                                        cwd=None, timeout=30, model=model, engine_cfg=cfg)
    except (AcpError, AcpTimeout, OSError) as e:
        msg = ("gemini unreachable at setup: %s — set GEMINI_API_KEY to use "
               "gemini-print" % e)
        sys.stderr.write("gemini-partner: CANARY (warn-only, not blocking) — %s\n" % msg)
        return {"reachable": False, "warnings": [msg]}
    warnings = []
    if not (rr.content or {}).get("text"):
        warnings.append("gemini answered but the response was empty (shape drift?)")
        sys.stderr.write("gemini-partner: CANARY DRIFT (warn-only, not blocking) — %s\n"
                         % warnings[-1])
    return {"reachable": True, "session": rr.session, "warnings": warnings}


def _canary_agy(cfg) -> dict:
    """Probe the live agy print surface (D18/D28): one `agy -p "ok"` and confirm the
    conversation id is still recoverable from the log (catches OAuth expiry AND
    log-format drift in one shot). Never blocks (D12) — a down/logged-out agy returns
    a warning that tells the user how to log in. Uses the PrintTransport seam, so the
    fake drives it in tests."""
    model = _cfgmod._agy_model_for(cfg, "review")
    try:
        rr = PrintTransport().run(composed="ok", mode="plan", session=None, cwd=None,
                                  timeout=30, model=model, engine_cfg=cfg)
    except (AcpError, AcpTimeout, OSError) as e:
        msg = ("agy unreachable / not logged in at setup: %s — run `agy` once to log "
               "in with Google (OAuth), or set GEMINI_API_KEY to use gemini-print" % e)
        sys.stderr.write("gemini-partner: AGY CANARY (warn-only, not blocking) — %s\n" % msg)
        return {"reachable": False, "warnings": [msg]}
    warnings = []
    if rr.session is None:
        warnings.append("agy conversation-id not recoverable from the log (format "
                        "drift?) — multi-round recall degrades to one-shot")
        sys.stderr.write("gemini-partner: AGY CANARY DRIFT (warn-only) — %s\n"
                         % warnings[-1])
    return {"reachable": True, "conversation_id_recovered": rr.session is not None,
            "warnings": warnings}


def _reap_worktrees(reg) -> int:
    """Remove orphan sandbox worktrees left by a crashed write (P5). Best-effort:
    try `git worktree remove`, then rmtree the dir. Returns the count reaped."""
    wt_base = reg._dir / "worktrees"
    if not wt_base.is_dir():
        return 0
    import shutil
    reaped = 0
    for child in list(wt_base.iterdir()):
        if not child.is_dir():
            continue
        try:
            subprocess.run(["git", "worktree", "remove", "--force", str(child)],
                           capture_output=True, text=True)
        except Exception:
            pass
        shutil.rmtree(child, ignore_errors=True)
        if not child.exists():
            reaped += 1
    return reaped


def main(argv=None) -> int:
    """Verb CLI. `gemini_companion.py <verb> ...`:
        review | adversarial-review | research | task   — run an advisory/coding job
        status <job_id> | result <job_id> | cancel <job_id>  — inspect/stop a job
        setup                                            — lane preflight (canary lands in P10)
    """
    import argparse
    ap = argparse.ArgumentParser(description="gemini partner lane")
    sub = ap.add_subparsers(dest="verb", required=True)

    for v in ("review", "adversarial-review", "research", "task"):
        sp = sub.add_parser(v)
        sp.add_argument("-p", "--prompt", required=True)
        sp.add_argument("--purpose", default=None)
        sp.add_argument("--plan", action="store_true", help="force read-only plan mode")
        sp.add_argument("--config", default=None)
        sp.add_argument("--skill", default=None,
                        help="inject a skill's methodology (SKILL.md + cited "
                             "rules/references, verbatim) as the preamble")
        sp.add_argument("--round", type=int, default=None, dest="round_n",
                        help="Claude-driven loop iteration (stamped on the job "
                             "registry; the loop is driven by Claude, not a hook)")
        sp.add_argument("--engine", choices=["gemini-print", "agy-print"], default=None,
                        help="pin the engine (disables cross-engine fallback; "
                             "default: the config's engine axis, auto→env-detect)")
        if v == "task":
            sp.add_argument("--background", action="store_true")
            sp.add_argument("--write", action="store_true",
                            help="request the sandbox_write path (P5)")

    for v in ("status", "result", "cancel"):
        sp = sub.add_parser(v)
        sp.add_argument("job_id")

    sub.add_parser("setup").add_argument("--config", default=None)

    args = ap.parse_args(argv)
    reg = JobRegistry()

    if args.verb in _VERB_PURPOSE:
        purpose = args.purpose or _VERB_PURPOSE[args.verb]
        write_flag = getattr(args, "write", False)
        background = getattr(args, "background", False)
        # RT-09: a background job must never carry a write REQUEST — no supervisor
        # is watching to apply/review the worktree diff. Refuse the explicit combo
        # rather than silently downgrade it.
        if background and write_flag:
            sys.stderr.write(
                "gemini-partner: refused — background + write is forbidden "
                "(RT-09): a detached worker cannot gate its own worktree diff\n")
            return 2

        cfg = _cfgmod.effective(_cfgmod.resolve(args.config))
        want_write = write_flag and cfg["write"] == "sandbox_write"
        if write_flag and not want_write:
            sys.stderr.write(
                "gemini-partner: refused — write requested but lane write=%s "
                "(set write: sandbox_write to enable the staging path)\n" % cfg["write"])
            return 2

        if want_write:
            # S5: an advisory role (review/critique/redteam/research/scout) never
            # writes — it reads and reports. Refuse before spawning.
            if _cfgmod.is_advisory(purpose):
                sys.stderr.write(
                    "gemini-partner: refused — advisory purpose %r cannot use the "
                    "write path (S5)\n" % purpose)
                return 2
            job_id = _new_job_id()
            # Build the stamp HERE so a failure record is provenance-stamped too
            # (D6: every outcome stamped) — _run_sandbox_write builds its own for
            # the success path (BL-155 tracks unifying the two). Stamp the engine that
            # WILL run (pin, else the auto resolution) so a failed agy write is not
            # mislabelled gemini.
            weng = getattr(args, "engine", None) or _cfgmod._resolve_engine(cfg)
            if weng == "agy-print":
                wengine, wmodel = "agy", _cfgmod._agy_model_for(cfg, purpose)
            else:
                wengine, wmodel = "gemini", _model_for(cfg, purpose)
            wstamp = {"reviewer_engine": wengine, "reviewer_model": wmodel,
                      "purpose": purpose, "mode": "write", "ts": _now_iso(),
                      "actor": resolve_actor()}
            reg.append({"job_id": job_id, "verb": args.verb, "purpose": purpose,
                        "status": "running", "mode": "write",
                        "model": wmodel, "provenance": wstamp})
            try:
                out = _run_sandbox_write(reg, job_id, purpose, args.prompt, cfg,
                                         engine=getattr(args, "engine", None))
            except (AcpError, AcpTimeout, OSError, subprocess.CalledProcessError) as e:
                # CalledProcessError covers a git failure in the write path (no
                # commit yet / non-repo cwd / disk full) — without it the job froze
                # at "running" with a traceback (review finding).
                reg.append({"job_id": job_id, "verb": args.verb, "purpose": purpose,
                            "status": "failed", "mode": "write", "reason": str(e),
                            "model": wmodel, "provenance": wstamp})
                sys.stderr.write("gemini-partner: sandbox write failed (%s)\n" % e)
                return 3
            reg.append({"job_id": job_id, "verb": args.verb, "purpose": purpose,
                        "status": "done", "mode": "write",
                        "model": out.provenance.get("reviewer_model"),
                        "provenance": out.provenance, "result": out.content,
                        "session": out.session})
            print(json.dumps({"job_id": job_id, "status": "done",
                              "provenance": out.provenance,
                              "escaped": out.content.get("escaped")}, ensure_ascii=False))
            return 0

        skill = getattr(args, "skill", None)
        if skill:
            # Fail loud if the named skill has no SKILL.md — never a silent
            # no-injection run that looks like success.
            import gemini_skill_inject as _gsi
            try:
                _gsi.resolve_skill(skill, skills_dir=_skill_skills_dir(),
                                   harness_root=_skill_harness_root())
            except _gsi.SkillNotFound as e:
                sys.stderr.write("gemini-partner: refused — %s\n" % e)
                return 2
        job_id, out = _run_job(reg, args.verb, purpose, args.prompt, "plan",
                               args.config, skill=skill,
                               round_n=getattr(args, "round_n", None),
                               engine=getattr(args, "engine", None))
        # Include the result (the actual findings/report) in the envelope, not just
        # provenance: an advisory verb that omitted `result` forced a second
        # `result <job_id>` fetch to see the findings, and a relayer that skipped
        # that second call silently returned an empty (provenance-only) envelope —
        # real findings could slip. The findings are now self-contained in one call.
        # Degraded/Inert carry no `content` field — getattr so a down/off lane prints
        # a clean envelope (result: null) instead of dying with an AttributeError.
        print(json.dumps({"job_id": job_id, "status": reg.latest(job_id)["status"],
                          "provenance": out.provenance,
                          "result": getattr(out, "content", None)},
                         ensure_ascii=False))
        return 0 if out.status in ("ok", "inert") else 3

    if args.verb in ("status", "result"):
        rec = reg.latest(args.job_id)
        if rec is None:
            sys.stderr.write("gemini-partner: no such job %s\n" % args.job_id)
            return 2
        if args.verb == "status":
            print(json.dumps({"job_id": args.job_id, "status": rec["status"]},
                             ensure_ascii=False))
        else:
            print(json.dumps({"job_id": args.job_id, "result": rec.get("result"),
                              "provenance": rec.get("provenance")}, ensure_ascii=False))
        return 0

    if args.verb == "cancel":
        rec = reg.latest(args.job_id)
        if rec is None:
            sys.stderr.write("gemini-partner: no such job %s\n" % args.job_id)
            return 2
        # Registry-only in v1: spawn-per-call means the job's ACP session lives in
        # the WORKER process, unreachable from a fresh client (an ACP cancel here
        # would just be a dead call). We record the cancellation; live-session
        # cancel (signalling the worker) is a v2 concern (dogfood finding).
        reg.append({"job_id": args.job_id, "verb": "cancel", "status": "cancelled"})
        print(json.dumps({"job_id": args.job_id, "status": "cancelled"}, ensure_ascii=False))
        return 0

    if args.verb == "setup":
        cfg = _cfgmod.effective(_cfgmod.resolve(args.config))
        reaped = _reap_worktrees(reg)
        canary = None
        canary_agy = None
        if cfg["master"] != "on":
            canary = {"skipped": "master off"}
        elif _cfgmod._auth_inert(cfg):
            # D25: engine=auto but NO credential at all — report inert-auth EARLY
            # instead of spawning two engines that both fail. STILL print how to
            # enable the lane (scenario-HIGH: never a silent abort).
            sys.stderr.write(
                "gemini-partner: INERT-AUTH — engine=auto but no credential found "
                "(no GEMINI_API_KEY and no agy login). To enable the lane: run `agy` "
                "once to log in with Google (agy-print), OR set GEMINI_API_KEY "
                "(gemini-print)\n")
            canary = {"inert_auth": True,
                      "hint": "run `agy` to log in, or set GEMINI_API_KEY"}
        else:
            # Probe the engine(s) the config will actually use (D28): auto → BOTH;
            # a pinned engine → just that one. The gemini result stays under `canary`
            # (back-compat), agy under `canary_agy`.
            axis = cfg.get("engine", "auto")
            if axis in ("auto", "gemini-print"):
                canary = _canary(cfg)
            if axis in ("auto", "agy-print"):
                canary_agy = _canary_agy(cfg)
        print(json.dumps({"master": cfg["master"], "mode": cfg["mode"],
                          "write": cfg["write"], "stop_review_gate": cfg["stop_review_gate"],
                          "reaped_worktrees": reaped, "canary": canary,
                          "canary_agy": canary_agy},
                         ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
