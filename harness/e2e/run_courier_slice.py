#!/usr/bin/env python3
"""run_courier_slice.py — end-to-end courier slice on a REAL temp HOME.

Exercises the scriptable acceptance of the hs-plugin-courier plan without an
interactive Claude Code session (memory: dogfood the real code, not a fake):

  E2  build the courier tree from a real pack tarball (the plugin "cache")
  E3  `harness setup` into a temp target repo under a fake HOME
        → engine home + `current`, per-project env in the TARGET's
          settings.local.json, hooks + marketplace + .harness skeleton, and the
          real ~/.claude/settings.json untouched
  E4  two-zone guard: a tool-Write into ${engine}/** BLOCKS (exit 2), a project
        .harness/ write PASSES — the REAL write_guard, shipped config
  E8  a newer cache → engine_skew_nudge advisory via the real dispatcher;
        `harness doctor` names it; `harness upgrade` clears it
  E10 `harness setup --uninstall` removes the wiring
  E9  self-host (HARNESS_BIN_ROOT UNSET) → both courier cores silent

Everything runs under HOME=<temp> so nothing touches the developer's machine.
Exit 0 = all checks passed; non-zero = a real defect in phases 2–6.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent
_REPO = _HARNESS.parent
for _p in (str(_HARNESS / "scripts"), str(_HARNESS / "install"), str(_HARNESS / "hooks"),
           str(_REPO / "release")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_PASS = []
_FAIL = []


def _check(name, ok, detail=""):
    (_PASS if ok else _FAIL).append(name)
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  — " + detail) if detail else ""))


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _build_cache(workdir: Path) -> Path:
    """Build a courier tree from an isolated fresh-manifest source (the 'cache')."""
    import build_manifest
    import pack
    import courier_tree
    src = workdir / "source"
    rels = subprocess.run(
        ["git", "-C", str(_REPO), "ls-files", "-z", "--", "harness/"],
        capture_output=True, text=True, check=True).stdout.split("\0")
    for rel in rels:
        if rel.strip() and (_REPO / rel).is_file():
            dst = src / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((_REPO / rel).read_bytes())
    _git(src, "init", "-q")
    _git(src, "-c", "user.email=e@e", "-c", "user.name=e", "add", "-A")
    _git(src, "-c", "user.email=e@e", "-c", "user.name=e", "commit", "-qm", "seed")
    build_manifest.main(["--root", str(src)])
    tarball = workdir / "bundle.tar.gz"
    pack.build_tarball(src, pack.manifest_files(src), tarball)
    cache = workdir / "cache"
    courier_tree.build_courier_tree(tarball, cache, repo_root=workdir / "outside")
    return cache


def _run_setup(home: Path, target: Path, cache_engine: Path, env_overrides):
    """Run harness_lifecycle.setup in a clean interpreter so engine_home() reads
    the fake HOME (the module caches nothing, but a subprocess is the honest
    global-layout test)."""
    code = (
        "import sys; sys.path[:0]=[r'%s', r'%s', r'%s']\n"
        "import harness_lifecycle as L\n"
        "print(__import__('json').dumps(L.setup(r'%s', source_engine=r'%s')))\n"
        % (_HARNESS / "scripts", _HARNESS / "install", _HARNESS / "hooks",
           target, cache_engine / "engine"))
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows: Path.home() prefers USERPROFILE over HOME
    env.pop("XDG_DATA_HOME", None)
    env.pop("HARNESS_BIN_ROOT", None)
    env.pop("HARNESS_DATA_ROOT", None)
    env.update(env_overrides or {})
    return subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, env=env)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="harness-courier-e2e-"))
    print("courier e2e slice in %s" % work)
    try:
        home = work / "home"
        home.mkdir()
        target = work / "target"
        target.mkdir()
        _git(target, "init", "-q")

        # E2 — build the cache
        cache = _build_cache(work)
        _check("E2 courier cache has bin/ + engine/",
               (cache / "bin" / "harness").is_file()
               and (cache / "engine" / "harness" / "scripts").is_dir())

        # E3 — setup
        r = _run_setup(home, target, cache, {})
        _check("E3 setup exit 0", r.returncode == 0, r.stderr[-300:])
        version = None
        if r.returncode == 0:
            version = json.loads(r.stdout.strip().splitlines()[-1])["version"]
        eh = home / ".local" / "share" / "harness"
        _check("E3 engine at engine_home/<v>",
               bool(version) and (eh / version / "harness" / "scripts").is_dir())
        _check("E3 current -> version",
               (eh / "current").is_symlink()
               and (eh / "current").resolve() == (eh / version).resolve() if version else False)
        sl_path = target / ".claude" / "settings.local.json"
        sl = json.loads(sl_path.read_text()) if sl_path.is_file() else {}
        sj_env_path = target / ".claude" / "settings.json"
        sj_env = json.loads(sj_env_path.read_text()) if sj_env_path.is_file() else {}
        _bin = sj_env.get("env", {}).get("HARNESS_BIN_ROOT")
        # resolve() both sides: on macOS the temp home lives under /tmp, a symlink to
        # /private/tmp, so setup wires the resolved form and a raw str compare misses.
        _check("E3 per-project HARNESS_BIN_ROOT in target settings.json",
               bool(_bin) and Path(_bin).resolve() == (eh / "current").resolve())
        _check("E3 real ~/.claude/settings.json untouched",
               not (home / ".claude" / "settings.json").exists())
        # hooks are wired into the target repo's settings.json (NEVER
        # settings.local.json — CC clobbers the latter on every permission approval)
        sj_path = target / ".claude" / "settings.json"
        sj = json.loads(sj_path.read_text()) if sj_path.is_file() else {}
        _check("E3 hooks wired into settings.json", bool(sj.get("hooks")))
        _check("E3 no hooks in settings.local.json", not sl.get("hooks"))
        _mk = (sl.get("extraKnownMarketplaces", {}).get("hs-local", {})
               .get("source", {}).get("path"))
        _check("E3 marketplace hs-local -> engine home",
               bool(_mk) and Path(_mk).resolve()
               == (eh / "current" / "harness" / "plugins").resolve())
        _check("E3 .harness skeleton seeded", (target / ".harness").is_dir())

        # E4 — two-zone guard: tool-Write into the engine BLOCKS (real write_guard)
        _e4_guard(eh, target, version)

        # E8 — skew advisory + doctor + upgrade
        if version:
            _e8_skew(home, eh, cache, version)

        # E10 — uninstall
        _e10_uninstall(home, target)

        # E9 — self-host silence
        _e9_self_host()

    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)

    print("\ncourier e2e: %d passed, %d failed" % (len(_PASS), len(_FAIL)))
    return 1 if _FAIL else 0


def _e4_guard(eh: Path, target: Path, version):
    wg = _HARNESS / "hooks" / "write_guard.py"

    def _wg(target_path):
        env = dict(os.environ)
        for k in ("HARNESS_ROOT", "HARNESS_DATA_ROOT", "HARNESS_HOOK_LOG_DIR",
                  "HARNESS_WRITE_GUARD_CONFIG", "HARNESS_HOOK_CONFIG",
                  "PYTEST_CURRENT_TEST"):
            env.pop(k, None)  # shipped config → guard ENABLED
        env["HARNESS_BIN_ROOT"] = str((eh / "current").resolve())
        env["CLAUDE_PROJECT_DIR"] = str(target)
        payload = {"session_id": "e2e", "tool_name": "Write",
                   "tool_input": {"file_path": target_path, "content": "x"}}
        return subprocess.run([sys.executable, str(wg)], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    if not version:
        _check("E4 guard (skipped — no engine)", False, "setup failed")
        return
    bin_target = str((eh / "current").resolve() / "harness" / "data" / "stage-policy.yaml")
    _check("E4 tool-Write into engine ${bin} BLOCKS (exit 2)",
           _wg(bin_target).returncode == 2)
    (target / ".harness" / "state").mkdir(parents=True, exist_ok=True)
    proj_target = str(target / ".harness" / "state" / "t.jsonl")
    _check("E4 legit project .harness/ write PASSES (exit 0)",
           _wg(proj_target).returncode == 0)


def _e8_skew(home: Path, eh: Path, cache: Path, version):
    # plant a newer cache in the fake HOME's plugin cache
    newer = (home / ".claude" / "plugins" / "cache" / "mkt" / "harness"
             / "9.9.9" / "engine" / "harness")
    newer.mkdir(parents=True)
    (newer / "release.json").write_text(json.dumps({"harness_version": "9.9.9"}))
    disp = _HARNESS / "hooks" / "hook_dispatch.py"
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows: Path.home() prefers USERPROFILE over HOME
    env["HARNESS_BIN_ROOT"] = str(eh / "current")
    env["TMPDIR"] = str(home / "tmp")
    (home / "tmp").mkdir(exist_ok=True)
    env["HARNESS_HOOK_CONFIG"] = str(_HARNESS / "data" / "harness-hooks.yaml")
    r = subprocess.run([sys.executable, str(disp), "SessionStart"],
                       input=json.dumps({"session_id": "e8", "source": "startup"}),
                       capture_output=True, text=True, env=env)
    _check("E8 skew advisory surfaces via dispatcher (9.9.9 + upgrade)",
           "9.9.9" in r.stdout and "upgrade" in r.stdout)


def _e10_uninstall(home: Path, target: Path):
    code = (
        "import sys; sys.path[:0]=[r'%s', r'%s', r'%s']\n"
        "import harness_lifecycle as L\n"
        "print(__import__('json').dumps(L.uninstall(r'%s')))\n"
        % (_HARNESS / "scripts", _HARNESS / "install", _HARNESS / "hooks", target))
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows: Path.home() prefers USERPROFILE over HOME
    env.pop("XDG_DATA_HOME", None)
    env.pop("HARNESS_BIN_ROOT", None)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    ok = r.returncode == 0
    if ok:
        # hooks + HARNESS_BIN_ROOT/HARNESS_DATA_ROOT are wired into settings.json
        # (never settings.local.json — CC clobbers the latter on every permission
        # approval), so that is where uninstall must strip them from. The
        # marketplace/enabledPlugins entries genuinely live only in
        # settings.local.json (CC's own plugin-management home).
        sj_path = target / ".claude" / "settings.json"
        sj = json.loads(sj_path.read_text()) if sj_path.is_file() else {}
        sl_path = target / ".claude" / "settings.local.json"
        sl = json.loads(sl_path.read_text()) if sl_path.is_file() else {}
        ok = not sj.get("hooks") \
            and "HARNESS_BIN_ROOT" not in (sj.get("env") or {}) \
            and "HARNESS_DATA_ROOT" not in (sj.get("env") or {}) \
            and "hs-local" not in (sl.get("extraKnownMarketplaces") or {}) \
            and not any(k.startswith("hs@") for k in (sl.get("enabledPlugins") or {}))
    _check("E10 uninstall removes per-project wiring", ok, r.stderr[-200:])


def _e9_self_host():
    for mod, entry in (("engine_root_inject", "core"), ("engine_skew_nudge", "core")):
        code = (
            "import sys; sys.path[:0]=[r'%s', r'%s']\n"
            "import os; os.environ.pop('HARNESS_BIN_ROOT', None)\n"
            "import %s as M\n"
            "print('NONE' if M.%s({'session_id':'x'}) is None else 'EMIT')\n"
            % (_HARNESS / "hooks", _HARNESS / "scripts", mod, entry))
        env = dict(os.environ)
        env.pop("HARNESS_BIN_ROOT", None)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        _check("E9 self-host %s silent (UNSET)" % mod, r.stdout.strip() == "NONE",
               r.stderr[-200:])


if __name__ == "__main__":
    raise SystemExit(main())
