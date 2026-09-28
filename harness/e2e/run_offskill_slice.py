#!/usr/bin/env python3
"""run_offskill_slice.py — e2e slice for the off-skill loop.

Exercises the FULL round-trip on a git-seeded temp-install, all via subprocess so
the transport is real and the real repo tree is never touched:

    disable -> git rename -> --list/--status/--chain -> hs:use proxy demand ->
    lens re-enable surfacing -> disabled_ref nudge -> disabled_skill router block ->
    re-enable round-trip (dep auto-restored, stash left clean).

`run_slice(root)` returns a dict of per-link booleans plus `ok`. `build_install(dest)`
assembles the temp tree. This is the automatable half of the phase's live verify; the
fresh-session probe (whether PreToolUse(Skill) fires for a fully-omitted name) is a
manual step recorded in the phase artifact — the same 3-path map also reaches the model
via the nudge and hs:use, so the deliverable never rests on the router hook alone.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_E2E = Path(__file__).resolve().parent
_HARNESS = _E2E.parent

_LEAF = "demo-leaf"
_MID = "demo-mid"
_DEP = "demo-dep"
_CHAIN = (_LEAF, _MID, _DEP)  # depth-2 so transitive dep-restore is exercised
_SESSIONS = ("off-s1", "off-s2", "off-s3")  # 3 distinct → crosses the re-enable floor

_MIN_DEPS_YAML = (
    "core_immutable: [use, find-skills, cleanup]\n"
    "skills:\n"
    "  use: { deps: [] }\n"
    "  find-skills: { deps: [] }\n"
    "  cleanup: { deps: [] }\n"
    "  %s: { deps: [%s] }\n"
    "  %s: { deps: [%s] }\n"
    "  %s: { deps: [] }\n" % (_LEAF, _MID, _MID, _DEP, _DEP)
)


def _skill_md(name: str) -> str:
    return (
        "---\n"
        "name: hs:%s\n"
        "description: Demo off-skill fixture for the e2e slice — exercises the "
        "disable/use/re-enable loop. Use when verifying the off-skill machinery.\n"
        "user-invocable: true\n"
        "metadata:\n"
        "  owner: harness\n"
        "  compliance-tier: knowledge\n"
        "---\n\n"
        "# hs:%s\n\nFixture body.\n" % (name, name)
    )


def _env(root: Path) -> dict:
    env = dict(os.environ)
    for k in ("PYTEST_CURRENT_TEST", "HARNESS_TELEMETRY_DISABLED", "HARNESS_HOOK_CONFIG",
              "HARNESS_ACTIVE_PLAN", "HARNESS_STAGE_POLICY", "HARNESS_SESSION_ID",
              "CI", "GITLAB_CI", "GITHUB_ACTIONS"):
        env.pop(k, None)
    env["HARNESS_ROOT"] = str(root)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env["HARNESS_STATE_DIR"] = str(root / "harness" / "state")
    env["HARNESS_HOOK_LOG_DIR"] = str(root / "harness" / "state" / "logs")
    env["HARNESS_USER"] = "off-slice"
    # the temp copy of the scripts/hooks is what runs — never the repo tree
    env["PYTHONPATH"] = os.pathsep.join([
        str(root / "harness" / "scripts"), str(root / "harness" / "hooks"),
        env.get("PYTHONPATH", "")])
    return env


def _run(root: Path, rel: str, *args, stdin: str = None):
    script = root / "harness" / rel
    return subprocess.run([sys.executable, str(script), *args], input=stdin,
                          capture_output=True, text=True, env=_env(root))


def _git(root: Path, *args):
    return subprocess.run(["git", "-c", "user.email=off@local", "-c", "user.name=off",
                           *args], cwd=str(root), capture_output=True, text=True)


def build_install(dest: Path) -> Path:
    """Assemble a git-seeded temp-install with the off-skill machinery + a 2-skill
    fixture chain (demo-leaf -> demo-dep). Real scripts/hooks/data are copied so the
    slice runs the real code without touching the repo tree; skill-deps.yaml is
    replaced with a minimal graph that owns the fixture skills."""
    root = Path(dest)
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("scripts", "hooks", "data"):
        shutil.copytree(_HARNESS / sub, root / "harness" / sub)
    (root / "harness" / "data" / "skill-deps.yaml").write_text(_MIN_DEPS_YAML, encoding="utf-8")

    skills = root / "harness" / "plugins" / "hs" / "skills"
    for name in ("use", "find-skills", "cleanup", _LEAF, _MID, _DEP):
        d = skills / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(_skill_md(name), encoding="utf-8")
    (root / "harness" / "plugins" / "hs" / "disabled-skills").mkdir(parents=True, exist_ok=True)
    (root / "harness" / "state").mkdir(parents=True, exist_ok=True)

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed off-skill fixture")
    return root


def _read_invocations(root: Path) -> list:
    # Union legacy sink + per-session shards (P2 shards demand rows carrying a
    # session to invocations-<disc>.jsonl).
    d = root / "harness" / "state" / "telemetry"
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("invocations*.jsonl")):
        if p.name.endswith(".bak"):
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _lens_reenable(root: Path) -> list:
    """Call lens_skill_usage.gather(root=...) out-of-process (it has no CLI) and
    return its reenable_candidates — the real read path hs:insights uses."""
    code = ("import json, lens_skill_usage as l;"
            "print(json.dumps(l.gather(root=%r).get('reenable_candidates', [])))" % str(root))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env=_env(root))
    try:
        return json.loads((proc.stdout or "[]").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return []


def run_slice(root: Path) -> dict:
    root = Path(root)
    plug = root / "harness" / "plugins" / "hs"
    s = {}

    # 1. disable the whole chain (dir-omit stash move)
    dis = _run(root, "scripts/hs_cli.py", "skills",
               "--disable", _LEAF, "--disable", _MID, "--disable", _DEP, "--root", str(root))
    s["disable_moved_to_stash"] = (
        dis.returncode == 0
        and not (plug / "skills" / _LEAF).exists()
        and (plug / "disabled-skills" / _LEAF / "SKILL.md").is_file())

    # 2. the move is a git RENAME, not delete+add (blame/history survive)
    _git(root, "add", "-A")
    st = _git(root, "status", "--porcelain=v1", "-M")
    s["git_rename_not_deletion"] = any(
        ln.startswith("R") and _LEAF in ln for ln in st.stdout.splitlines())

    # 3. the disabled-state query surfaces it correctly
    lst = _run(root, "scripts/disabled_skills.py", "--list", "--root", str(root))
    stt = _run(root, "scripts/disabled_skills.py", "--status", _LEAF, "--root", str(root))
    chn = _run(root, "scripts/disabled_skills.py", "--chain", _LEAF, "--root", str(root))
    chain_out = chn.stdout.splitlines()
    s["list_shows_off"] = _LEAF in lst.stdout
    s["status_disabled"] = stt.stdout.strip() == "disabled"
    # transitive closure: enabling the leaf must know to pull BOTH its dep and the
    # dep-of-dep, so both appear in the disabled chain (depth-2 coverage)
    s["chain_closure"] = _MID in chain_out and _DEP in chain_out

    # 4. the hs:use proxy loads the off skill's prose FROM the stash
    stash_md = plug / "disabled-skills" / _LEAF / "SKILL.md"
    s["stash_prose_readable"] = stash_md.is_file() and bool(stash_md.read_text(encoding="utf-8").strip())

    # 5. ...and records demand, target-keyed, once per distinct session
    for sess in _SESSIONS:
        _run(root, "scripts/emit_disabled_demand.py", "--skill", "hs:%s" % _LEAF,
             "--via", "proxy_run", "--session", sess)
    rows = [r for r in _read_invocations(root) if r.get("via") == "proxy_run"]
    s["demand_rows_target_keyed"] = (
        len(rows) == len(_SESSIONS)
        and all(r.get("skill") == "hs:%s" % _LEAF and r.get("proxy_invoked") is True
                for r in rows))

    # 6. the lens surfaces the off skill as a re-enable candidate (>= 3 sessions)
    cands = {c.get("skill") for c in _lens_reenable(root)}
    s["lens_surfaces_demand"] = _LEAF in cands

    # 7. a prose reference to the off skill trips the advisory nudge with /hs:use
    nud = _run(root, "hooks/disabled_ref_nudge.py",
               stdin=json.dumps({"prompt": "hand off to hs:%s next" % _LEAF}))
    s["nudge_fires_with_use"] = "/hs:use %s" % _LEAF in nud.stderr

    # 8. a RAW Skill call on the off skill is blocked with the 3-path map
    rtr = _run(root, "hooks/disabled_skill_router.py",
               stdin=json.dumps({"tool_input": {"skill": "hs:%s" % _LEAF}, "session_id": "off-s9"}))
    s["router_blocks_with_map"] = (
        rtr.returncode == 2
        and "/hs:use %s" % _LEAF in rtr.stderr
        and "--enable %s" % _LEAF in rtr.stderr)

    # 9. re-enable round-trips the leaf AND auto-restores its transitive deps,
    # leaving no stash residue for any link in the chain
    en = _run(root, "scripts/hs_cli.py", "skills", "--enable", _LEAF, "--root", str(root))
    s["enable_roundtrip"] = en.returncode == 0 and all(
        (plug / "skills" / n / "SKILL.md").is_file()
        and not (plug / "disabled-skills" / n).exists() for n in _CHAIN)

    s["ok"] = all(v for k, v in s.items() if k != "ok")
    return s


def main() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="harness-offskill-"))
    print("off-skill e2e slice in %s (subprocess transport, temp-install)" % tmp)
    try:
        root = build_install(tmp / "proj")
        summary = run_slice(root)
        for k, v in summary.items():
            if k == "ok":
                continue
            print("  %s %s" % ("✓" if v else "✗", k))
        print("\noff-skill slice:", "PASS" if summary["ok"] else "FAIL")
        return 0 if summary["ok"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
