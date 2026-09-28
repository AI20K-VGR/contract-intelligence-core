#!/usr/bin/env python3
"""harness_lifecycle.py — the courier's on-PATH lifecycle tool.

Verbs (surfaced by the `harness` wrapper on PATH):

  setup [--pin] [--harden-bin] [--uninstall]
      Copy the engine out of the plugin cache into the stable engine home
      (~/.local/share/harness/<version>), verify it BEFORE repointing `current`
      (red-team F5), then wire the CURRENT repo per-project: HARNESS_BIN_ROOT into
      settings.local.json (F3 — never the global ~/.claude), hooks, the plugin
      marketplace (absolute path into the engine home), and the .harness/ skeleton.
  upgrade
      Copy + verify + swap `current` to the cache version, side-by-side with the
      old one. Does NOT touch repo wiring. A live session on `current` sees the new
      engine from its next hook call (F10 — session-pin is a backlog item).
  version   — engine-home version, cache version, and which source is running.
  path [rel]— print the engine root (or <root>/<rel>) — a deterministic net for prose.
  doctor    — INTEGRITY check (manifest-hash of the engine home, F8) + advisory
              cache↔home skew (DEC handshake: advisory, never a hard block).

Audience: this is a shipped, on-PATH tool (distinct from hs_cli.py, the in-repo
dev CLI). It reuses the installer's global-mode wiring helpers verbatim.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

_HERE = Path(__file__).resolve()
_SCRIPTS = _HERE.parent
_INSTALL = _HERE.parent.parent / "install"
for _p in (str(_SCRIPTS), str(_INSTALL)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import harness_paths  # noqa: E402
import verify_install  # noqa: E402


class LifecycleError(RuntimeError):
    """Actionable, caller-facing failure — the wrapper surfaces the message."""


# --- engine resolution ---------------------------------------------------


def _cache_engine(source_engine=None) -> Path:
    """The engine to copy FROM (the plugin cache). Explicit arg > the wrapper's
    HARNESS_COURIER_CACHE export > this file's own engine root (…/scripts →
    engine root is two parents up from harness/)."""
    if source_engine:
        return Path(source_engine)
    env = os.environ.get("HARNESS_COURIER_CACHE")
    if env:
        return Path(env)
    return _HERE.parent.parent.parent  # scripts -> harness -> <engine root>


def _read_version(engine: Path) -> str:
    rj = Path(engine) / "harness" / "release.json"
    if not rj.is_file():
        raise LifecycleError(
            "source engine has no harness/release.json at %s — not a courier "
            "engine" % engine)
    try:
        data = json.loads(rj.read_text(encoding="utf-8"))
    except ValueError as e:
        raise LifecycleError(
            "source engine release.json is not valid JSON (%s) — truncated or corrupt "
            "download? re-run `harness setup`" % e)
    if not isinstance(data, dict):
        raise LifecycleError("source engine release.json is not a JSON object")
    v = data.get("harness_version")
    if not v:
        raise LifecycleError("source engine release.json carries no harness_version")
    if not isinstance(v, str) or not _is_safe_version_segment(v):
        raise LifecycleError(
            "source engine release.json's harness_version (%r) is not usable as "
            "a path segment — expected a plain version string" % (v,))
    return v


def _is_safe_version_segment(v: str) -> bool:
    """harness_version is used directly as a path segment (the F5 staging prefix
    and engine_home/<version>) — reject anything that is not a single flat
    component: a path separator would let it escape the flat engine-home layout,
    and `.`/`..`/a leading `.` would collide with `current` or the hidden staging
    dirs `_installed_versions` already excludes by name."""
    if v in (".", ".."):
        return False
    if "/" in v or "\\" in v:
        return False
    if v.startswith("."):
        return False
    return True


def _semver_key(v):
    """Sort key for a harness_version string, via `packaging.version.Version` so
    rc1 < rc2 < rc10 < final compare NUMERICALLY — a hand-rolled comparator that
    dot-split the pre-release missed this: this repo writes the single identifier
    "rc10" (not "rc.10"), which is not `.isdigit()` and fell into a lexical-string
    branch where "rc10" < "rc2". Build metadata (+...) is stripped BEFORE handing the
    string to Version — semver ignores it, but PEP 440 gives a local version (+build)
    meaning (it sorts ABOVE the base), which would silently change ordering behaviour.

    MUST stay total: `harness_version` is repo-controlled, but doctor/upgrade must
    never crash the diagnostic verb on one that is not PEP-440-shaped (e.g. a test
    fixture's "9.9.9-cache"). A string `Version` rejects is coerced into the closest
    numeric base and treated as a pre-release of it (sorts below that base's final) —
    never raises. MUST match engine_skew_nudge._semver_key so `harness upgrade`'s
    direction guard and the skew nudge agree (a test pins the two together)."""
    s = str(v).split("+")[0]
    try:
        return Version(s)
    except InvalidVersion:
        base = s.split("-", 1)[0]
        parts = []
        for chunk in base.split("."):
            num = "".join(ch for ch in chunk if ch.isdigit())
            parts.append(num if num else "0")
        while len(parts) < 3:
            parts.append("0")
        try:
            return Version(".".join(parts[:3]) + ".dev0")
        except InvalidVersion:
            return Version("0.0.0.dev0")


def _real_drift(root: Path) -> list:
    """The hard-drift (rel, problem) tuples a legit engine must not have — verify
    problems minus the tolerated-localized set. `split_localized` returns
    (hard, localized); we want hard."""
    problems = verify_install.verify(Path(root))
    hard, _localized = verify_install.split_localized(problems)
    return hard


def _fmt_drift(drift) -> list:
    return ["%s: %s" % (rel, prob) for rel, prob in drift]


# --- install a version (copy -> verify -> swap) --------------------------


def _install_version(source_engine: Path, *, repoint=True,
                     allow_downgrade=False) -> tuple:
    """Copy source engine into engine_home/<version> via a verified staging dir,
    optionally repoint `current`. Returns (version, version_dir, engine_home).

    repoint=False (used by `setup --pin`) installs the version dir but leaves
    `current` untouched — the pinned repo wires straight to the version dir.
    allow_downgrade=False makes the repoint forward-only: it never rolls the shared
    `current` back to an older version (so a `setup` from a project with an older
    plugin cache cannot silently downgrade every other project's engine)."""
    source = Path(source_engine)
    version = _read_version(source)
    eh = harness_paths.engine_home()
    eh.mkdir(parents=True, exist_ok=True)

    # F5: copy to a hidden staging dir, verify, and ONLY THEN swap into place.
    stage = Path(tempfile.mkdtemp(dir=eh, prefix=".%s.tmp." % version))
    try:
        try:
            shutil.copytree(source / "harness", stage / "harness")
        except OSError as e:
            # a shutil.Error (unreadable cache file / NFS hiccup) is an OSError, not a
            # LifecycleError — wrap it so the wrapper surfaces an actionable message
            # instead of a raw traceback (mirrors the os.replace wrapping below).
            raise LifecycleError(
                "could not copy the source engine from %s: %s" % (source, e))
        drift = _real_drift(stage)
        if drift:
            raise LifecycleError(
                "engine verify failed before install (F5) — refusing to repoint "
                "`current`. First drift(s): %s" % "; ".join(_fmt_drift(drift[:5])))
        version_dir = eh / version
        # Same-version reinstall of a CLEAN engine → idempotent no-op: do NOT
        # rmtree+recopy the existing version_dir. `os.replace` cannot atomically
        # overwrite a non-empty dir on POSIX, so a rmtree-first would blow a
        # FileNotFoundError window through `current` for any LIVE session (the
        # multi-project global install this courier exists for) reading the engine
        # during the gap. If the installed copy already verifies clean, keep it and
        # just (re)point `current`. Only a MISSING or CORRUPT version_dir is replaced
        # (a repair — the engine is already broken there, so the brief window is moot).
        if version_dir.exists() and not _real_drift(version_dir):
            _force_rmtree(stage)  # staged copy is redundant
        else:
            try:
                if version_dir.exists():
                    # Re-check under the race: a concurrent first-install of the SAME
                    # version can fill version_dir with a CLEAN copy between the outer
                    # check and here. Don't destroy it (a live session may be reading
                    # it) — accept it as an idempotent success. Only a genuinely
                    # corrupt dir is repaired.
                    if not _real_drift(version_dir):
                        _force_rmtree(stage)
                        if repoint:
                            _repoint_current(eh, version, allow_downgrade=allow_downgrade)
                        return version, version_dir, eh
                    _force_rmtree(version_dir)  # may be read-only after --harden-bin
                os.replace(stage, version_dir)  # atomic within engine_home
            except OSError as e:
                # Lost the swap race after our checks (ENOTEMPTY): if a racer's copy
                # now verifies clean, succeed idempotently rather than raising a
                # misleading "hardened engine" error (nothing was hardened).
                if version_dir.exists() and not _real_drift(version_dir):
                    _force_rmtree(stage)
                else:
                    raise LifecycleError(
                        "could not install version %s at %s: %s — a hardened engine may "
                        "need `chmod -R u+w %s` before re-installing"
                        % (version, version_dir, e, version_dir))
    except Exception:
        _force_rmtree(stage)
        raise
    if repoint:
        _repoint_current(eh, version, allow_downgrade=allow_downgrade)
    return version, version_dir, eh


def _force_rmtree(path: Path) -> None:
    """rmtree that survives read-only dirs left by --harden-bin. 0o555 strips the
    write bit a DIRECTORY needs to unlink its children, so restore write on every
    directory (bottom-up not required — 0o555 stays traversable, so the walk can
    list them) before removing."""
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return
    for p in path.rglob("*"):
        if p.is_dir() and not p.is_symlink():
            try:
                os.chmod(p, 0o700)
            except OSError:
                pass
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    shutil.rmtree(path, ignore_errors=True)


def _repoint_current(engine_home: Path, version: str, *,
                     allow_downgrade=False) -> None:
    """Atomically repoint `current` → version. A live session resolving the engine
    through `current` during an upgrade must never see it missing, so we build a
    temp symlink and os.replace() it over the old one (atomic rename) rather than
    unlink-then-relink (which leaves a window with no `current`).

    Forward-only (allow_downgrade=False): if `current` already points at a NEWER
    version, leave it — `current` is the shared engine for every non-pinned project,
    so a `setup` from a project with an older plugin cache must not silently roll it
    back and break the others."""
    cur = engine_home / "current"

    def _swap(target: str) -> None:
        tmp = engine_home / (".current.tmp.%d" % os.getpid())
        try:
            if tmp.is_symlink() or tmp.exists():
                tmp.unlink()
            tmp.symlink_to(target)  # relative to engine_home
            os.replace(tmp, cur)    # atomic swap over the existing symlink
        except OSError as e:
            # No text-pointer fallback: HARNESS_BIN_ROOT=<home>/current resolves by
            # following a symlink, so a text file there would silently break every
            # resolver. Fail loud instead of pretending to degrade gracefully.
            try:
                if tmp.is_symlink() or tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise LifecycleError(
                "cannot create the `current` symlink at %s (%s) — this filesystem may "
                "not support symlinks, which the courier's engine home requires."
                % (cur, e))

    if not allow_downgrade:
        # forward-only relative to the NEWEST installed version, not just `current`
        # — a pin-only home has no `current` yet still must not get one pointing at
        # something older than a version already on disk.
        floor = _home_floor_version(engine_home)
        if floor and _semver_key(version) < _semver_key(floor):
            # Refuse to point `current` at the requested (older) version — but do NOT
            # leave `current` STRANDED below the newest installed engine. A newer
            # version installed via `--pin` raises the floor without advancing
            # `current`, so a later non-pin setup of a middle version hits this branch
            # with `current` still stale/below (or absent/dangling). Heal it UP to the
            # floor instead of returning blind (else the repo silently runs an older
            # engine than it just installed, with no in-tool remediation).
            cur_name = None
            if cur.is_symlink():
                try:
                    cur_name = Path(os.readlink(cur)).name
                except OSError:
                    cur_name = None
            if cur_name is None or _semver_key(cur_name) < _semver_key(floor):
                _swap(floor)
            return  # never point `current` below the newest installed engine
    _swap(version)
    if not allow_downgrade:
        # Concurrency heal: the forward-only guard above reads the floor and then swaps
        # with no lock, so a racer installing+repointing a NEWER version in that window
        # could leave us having just clobbered `current` back to an older version. Never
        # leave `current` below the newest installed engine — re-read and heal forward.
        # Lock-free by design (mirrors the same-version install race's idempotency); the
        # residual micro-window before the heal only ever exposes an OLDER-but-VALID
        # engine to a live session, which self-corrects here on convergence.
        newest = _home_floor_version(engine_home)
        if newest and _semver_key(version) < _semver_key(newest):
            _swap(newest)


# --- repo wiring (reuses the installer's global-mode helpers) ------------


def _wire_target(target: Path, version_dir: Path, bin_root_value: str,
                 *, harden_bin: bool) -> None:
    import install as installer  # noqa: E402
    import _wire_env  # noqa: E402
    import bootstrap  # noqa: E402
    import _harden_bin  # noqa: E402

    registration = installer.load_registration(version_dir)
    result = {"actions": [], "skipped_events": [], "warnings": [],
              "problems": [], "ok": True}
    # hooks -> settings.json, pointing at $HARNESS_BIN_ROOT (global mode). The
    # `local` arg is vestigial: _wire_settings always targets settings.json now
    # (CC clobbers settings.local.json on every permission approval and would wipe
    # the hooks — the failure that bit a fresh install twice).
    installer._wire_settings(target, registration, False, result, False, mode="global")
    # HARNESS_BIN_ROOT + HARNESS_DATA_ROOT per-project (F3) into settings.json —
    # never the global ~/.claude, and no longer settings.local.json (same clobber
    # reason). Wire the data root too (mirrors --global): the Bash-tool env carries
    # no CLAUDE_PROJECT_DIR, so without this the injected settings env alone could
    # not resolve state and a strict data_root() caller would fall to the
    # fail-closed marker whenever the SessionStart seed had not fired.
    _wire_env.wire_env(target, bin_root=bin_root_value,
                       data_root=str(target / ".harness"))
    # private .harness/ data skeleton
    bootstrap.ensure_skeleton(target / ".harness")
    # marketplace: an ABSOLUTE directory-source into the engine home (the repo has
    # no harness/plugins of its own under the courier), so the relative path the
    # per-project installer writes would not resolve.
    _wire_courier_marketplace(
        target, plugins_path=bin_root_value + "/harness/plugins",
        engine_for_names=version_dir)
    if harden_bin:
        _harden_bin.harden_bin(version_dir)


def _wire_courier_marketplace(target: Path, *, plugins_path: str,
                              engine_for_names: Path) -> None:
    from _components import _marketplace_plugins, MARKETPLACE, SPINE_PLUGIN
    from _settings import _settings_path, _load_settings, _write_settings

    names = _marketplace_plugins(Path(engine_for_names)) or [SPINE_PLUGIN]
    path = _settings_path(Path(target), True)  # settings.local.json
    settings = _load_settings(path)
    mk = dict(settings.get("extraKnownMarketplaces") or {})
    mk[MARKETPLACE] = {"source": {"source": "directory", "path": plugins_path}}
    settings["extraKnownMarketplaces"] = mk
    ep = dict(settings.get("enabledPlugins") or {})
    for n in names:
        ep["%s@%s" % (n, MARKETPLACE)] = True
    settings["enabledPlugins"] = ep
    _write_settings(path, settings, False)


# --- verbs ---------------------------------------------------------------


def setup(target_root, *, source_engine=None, pin=False, harden_bin=False) -> dict:
    source = _cache_engine(source_engine)
    # A courier setup serves the shared binary via env-resolve — it must NOT overlay
    # a project that already carries its own per-project harness/ tree (split-brain:
    # two trees, ambiguous which the guards resolve). Refuse EARLY, before any engine
    # install or wiring, mirroring install.py --global. Self-host/dogfood (target IS
    # the source engine) is exempt — its harness/ tree is the source, not a stale
    # overlay — matched by resolve-equality (install.py's source_is_target).
    tgt = Path(target_root).resolve()
    if (tgt / "harness").exists() and tgt != source.resolve():
        raise LifecycleError(
            "a per-project harness/ tree already exists at %s — a courier setup "
            "serves the shared binary via env and must not overlay it. Uninstall "
            "the per-project harness first, then re-run `harness setup`." % tgt)
    # --pin wires the repo straight to the version dir, so DON'T touch the shared
    # `current` (its contract: "not the moving current"). A non-pinned setup repoints
    # `current` FORWARD-ONLY — installing from an older plugin cache must not roll the
    # shared engine back for every other project.
    version, version_dir, eh = _install_version(source, repoint=not pin)
    if not pin and not (eh / "current").exists():
        # Forward-only left NO `current` (this non-pin setup installed a version
        # OLDER than one already pinned in the home, so the repoint was skipped). A
        # non-pin setup MUST still establish the shared pointer — point it at the
        # NEWEST installed engine (never a downgrade, it IS the newest), otherwise
        # `bin_root_value=<eh>/current` below would be a DANGLING path and
        # `_wire_target`/`load_registration` would crash with a raw FileNotFoundError.
        floor = _home_floor_version(eh)
        if floor:
            _repoint_current(eh, floor)
    bin_root_value = str(version_dir) if pin else str(eh / "current")
    # Wire hooks + marketplace from the engine the repo will ACTUALLY resolve
    # (bin_root_value), NOT version_dir: on a non-pin setup from an older cache the
    # forward-only guard leaves `current` at a NEWER version, so reading registration
    # from the older version_dir would wire hooks that the running engine dropped and
    # miss the gates the running engine added. For --pin they coincide.
    wiring_engine = Path(bin_root_value).resolve()
    _wire_target(Path(target_root), wiring_engine, bin_root_value,
                 harden_bin=harden_bin)
    return {"version": version, "version_dir": str(version_dir),
            "current": str(eh / "current"), "bin_root": bin_root_value,
            "engine_home": str(eh), "pinned": pin}


def upgrade(*, source_engine=None, allow_downgrade=False) -> dict:
    source = _cache_engine(source_engine)
    cache_v = _read_version(source)
    eh = harness_paths.engine_home()
    # `upgrade` only moves FORWARD relative to the NEWEST installed version (not just
    # `current` — a pin-only home has no `current` but still must not be downgraded).
    floor = _home_floor_version(eh)
    if floor and not allow_downgrade and _semver_key(cache_v) < _semver_key(floor):
        raise LifecycleError(
            "refusing to downgrade the engine home from %s to the cache's %s — "
            "`harness upgrade` only moves forward. To pin an older version "
            "deliberately, run `harness setup --pin` from that version's cache."
            % (floor, cache_v))
    version, version_dir, eh = _install_version(source, allow_downgrade=allow_downgrade)
    return {"version": version, "version_dir": str(version_dir),
            "current": str(eh / "current"),
            "note": ("a live session on `current` picks up this engine on its "
                     "next hook call; version-pin per session is a backlog item")}


def uninstall(target_root) -> dict:
    """Remove the per-project wiring this tool wrote. Hooks + HARNESS_BIN_ROOT /
    HARNESS_DATA_ROOT are wired into settings.json (never settings.local.json —
    CC clobbers the latter on every permission approval), while the courier
    marketplace/enabledPlugins entries are CC's own plugin-management home and
    genuinely live only in settings.local.json — so both files are stripped, each
    of what it actually carries (mirrors install.py._uninstall_settings' both-
    files loop). The engine home is NOT auto-removed — it may serve other repos —
    so its path is reported for manual cleanup."""
    from _settings import _settings_path, _load_settings, _write_settings
    from _components import MARKETPLACE
    import install as installer

    target = Path(target_root)
    touched = []
    for is_local in (False, True):
        path = _settings_path(target, is_local)
        if not path.is_file():
            continue
        settings = _load_settings(path)
        changed = False

        stripped = installer.strip_harness_hooks(settings.get("hooks") or {})
        if stripped != (settings.get("hooks") or {}):
            if stripped:
                settings["hooks"] = stripped
            else:
                settings.pop("hooks", None)
            changed = True

        env = dict(settings.get("env") or {})
        if "HARNESS_BIN_ROOT" in env or "HARNESS_DATA_ROOT" in env:
            env.pop("HARNESS_BIN_ROOT", None)
            env.pop("HARNESS_DATA_ROOT", None)
            if env:
                settings["env"] = env
            else:
                settings.pop("env", None)
            changed = True

        if is_local:
            mk = dict(settings.get("extraKnownMarketplaces") or {})
            if MARKETPLACE in mk:
                mk.pop(MARKETPLACE, None)
                if mk:
                    settings["extraKnownMarketplaces"] = mk
                else:
                    settings.pop("extraKnownMarketplaces", None)
                changed = True
            ep = settings.get("enabledPlugins") or {}
            new_ep = {k: v for k, v in ep.items() if not k.endswith("@%s" % MARKETPLACE)}
            if new_ep != ep:
                if new_ep:
                    settings["enabledPlugins"] = new_ep
                else:
                    settings.pop("enabledPlugins", None)
                changed = True

        if changed:
            _write_settings(path, settings, False)
            touched.append(str(path))

    eh = harness_paths.engine_home()
    left = [str(eh)] if eh.exists() else []
    return {"unwired": touched, "left_for_manual_removal": left}


def _installed_versions(eh: Path) -> list:
    """Version dirs actually present in the engine home (excludes `current` + the
    hidden staging dirs). A --pin-only home has these but no `current`."""
    if not eh.is_dir():
        return []
    out = []
    for p in sorted(eh.iterdir()):
        if p.name == "current" or p.name.startswith("."):
            continue
        if (p / "harness" / "release.json").is_file():
            out.append(p.name)
    return out


def _home_floor_version(eh: Path):
    """The NEWEST version installed in the engine home (via version dirs), or None.
    The forward-only guards key off this, not `current` alone — a pin-only home has
    installed versions but no `current`, and neither `upgrade` nor a repoint may
    default the home to something OLDER than what is already on disk."""
    installed = _installed_versions(eh)
    return max(installed, key=_semver_key) if installed else None


def version_info(*, source_engine=None) -> dict:
    eh = harness_paths.engine_home()
    home_v = _maybe_version(eh / "current")
    # A --pin-only home has version dirs but no `current` — report the newest
    # installed so `harness version` isn't blank after a pinned setup.
    installed = _installed_versions(eh)
    if home_v is None and installed:
        home_v = max(installed, key=_semver_key)
    cache = _cache_engine(source_engine)
    cache_v = _maybe_version(cache)
    running = (os.environ.get("HARNESS_BIN_ROOT")
               or os.environ.get("HARNESS_COURIER_CACHE") or str(_HERE))
    return {"home_version": home_v, "cache_version": cache_v,
            "running_source": running, "installed": installed,
            "current_set": (eh / "current").exists()}


def _maybe_version(engine_root: Path):
    rj = Path(engine_root) / "harness" / "release.json"
    if not rj.is_file():
        return None
    try:
        data = json.loads(rj.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    # a wrong-shape release.json (JSON list/scalar) makes .get() raise AttributeError —
    # this is best-effort version info, so degrade to None rather than crash version/doctor.
    return data.get("harness_version") if isinstance(data, dict) else None


def path_of(rel=None) -> str:
    root = os.environ.get("HARNESS_BIN_ROOT") or str(harness_paths.engine_current())
    if rel:
        return str(Path(root) / rel)
    return root


def doctor(*, source_engine=None, capture=False):
    lines = []
    eh = harness_paths.engine_home()
    # Check the engine THIS repo actually resolves — HARNESS_BIN_ROOT (which a
    # pinned repo sets to its own version dir) wins over the shared `current`.
    # Otherwise `doctor` would give a pinned repo a clean bill of health while
    # verifying a DIFFERENT (current) engine (the F8 same-version-tamper blind spot).
    raw = os.environ.get("HARNESS_BIN_ROOT")
    cur = None
    if raw:
        try:
            cur = Path(raw).resolve()
        except Exception:  # noqa: BLE001 — a symlink loop / unresolvable root must NOT
            # crash the diagnostic verb (doctor is what you run WHEN things are broken);
            # mirror engine_root_inject._resolved_global_root and report it as a failure.
            cur = None
    else:
        cur = eh / "current"
    rc = 0
    if cur is not None and (cur / "harness" / "manifest.json").is_file():
        drift = _real_drift(cur)
        if drift:
            rc = 1
            lines.append("integrity: %d file(s) drifted in the engine home:"
                         % len(drift))
            lines.extend("  " + d for d in _fmt_drift(drift[:20]))
        else:
            lines.append("integrity: OK — engine home matches its manifest")
    elif raw:
        # HARNESS_BIN_ROOT is set (a pinned/global repo) but the engine it resolves
        # is broken — either unresolvable (symlink loop / bad path) or present with NO
        # manifest. Both are a failure the repo actually runs on, NOT a healthy pin-only
        # home. Report it as rc=1.
        rc = 1
        if cur is None:
            lines.append("integrity: HARNESS_BIN_ROOT (%s) is unresolvable — a symlink "
                         "loop or bad path; run `harness setup` to repair the wiring"
                         % raw)
        else:
            lines.append("integrity: the resolved engine at %s has no manifest — "
                         "corrupt or incomplete; run `harness setup` or `harness upgrade`"
                         % cur)
    else:
        installed = _installed_versions(eh)
        if installed:
            # a --pin-only home has version dirs but no `current` — that is NOT
            # "nothing installed", so don't tell the user to re-run setup.
            lines.append(
                "engine: %d version(s) installed (%s) but no shared `current` "
                "pointer — pinned setups only. Run `harness setup` (non-pin) to set "
                "`current`." % (len(installed), ", ".join(installed)))
        else:
            lines.append("integrity: no engine installed at %s — run `harness setup`"
                         % cur)
    info = version_info(source_engine=source_engine)
    # skew advice must key off the SAME reference the upgrade/repoint guards enforce
    # (max-installed), not version_info's current-preferred home_version — otherwise
    # doctor advises `harness upgrade` for a version upgrade then refuses.
    cv, hv = info["cache_version"], _home_floor_version(eh)
    if cv and hv and _semver_key(cv) > _semver_key(hv):
        # only advise upgrade when the cache is genuinely NEWER — same direction as
        # engine_skew_nudge. Advising it on an older cache would drive a downgrade.
        lines.append(
            "skew: cache=%s is newer than home=%s (advisory) — run `harness "
            "upgrade` to apply the cache version to the engine home" % (cv, hv))
    elif cv and hv and _semver_key(cv) < _semver_key(hv):
        lines.append(
            "note: the engine home (%s) is newer than the plugin cache (%s); "
            "`harness upgrade` will NOT downgrade it. Pin the older version with "
            "`harness setup --pin` if you intend to roll back." % (hv, cv))
    report = "\n".join(lines)
    if capture:
        return rc, report
    print(report)
    return rc


# --- CLI -----------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="harness", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)

    s = sub.add_parser("setup", help="install the engine + wire this repo")
    s.add_argument("--pin", action="store_true",
                   help="wire this repo to the version dir, not the moving `current`")
    s.add_argument("--harden-bin", action="store_true",
                   help="strip write bits from the installed engine")
    s.add_argument("--uninstall", action="store_true",
                   help="remove this repo's harness wiring")

    sub.add_parser("upgrade", help="copy+verify+swap `current` to the cache version")
    sub.add_parser("version", help="engine-home / cache versions + running source")
    p = sub.add_parser("path", help="print the engine root (or <root>/<rel>)")
    p.add_argument("rel", nargs="?", default=None)
    sub.add_parser("doctor", help="integrity + advisory skew health check")

    args = ap.parse_args(argv)
    try:
        if args.verb == "setup":
            if args.uninstall:
                res = uninstall(Path.cwd())
                print(json.dumps(res, indent=2))
                if res["left_for_manual_removal"]:
                    print("\nEngine home left in place (may serve other repos):")
                    for p_ in res["left_for_manual_removal"]:
                        print("  rm -rf %s   # only if no other repo uses it" % p_)
                return 0
            res = setup(Path.cwd(), pin=args.pin, harden_bin=args.harden_bin)
            print(json.dumps(res, indent=2))
            print("\nRestart the Claude Code session so the wired env takes effect.")
            return 0
        if args.verb == "upgrade":
            print(json.dumps(upgrade(), indent=2))
            return 0
        if args.verb == "version":
            print(json.dumps(version_info(), indent=2))
            return 0
        if args.verb == "path":
            print(path_of(args.rel))
            return 0
        if args.verb == "doctor":
            return doctor()
    except LifecycleError as e:
        sys.stderr.write("harness: %s\n" % e)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
