#!/usr/bin/env python3
"""_prompts.py — interactive install prompts (extracted from install.py).

Pure terminal UX: read the reviewer roster / component selection / opt-in
toggles from a TTY. No install orchestration and no InstallError — the caller
acts on the returned values. Kept separate so install.py reads as orchestration.
"""
import subprocess
import sys


def _prompt_statusline() -> bool:
    """Ask once whether to enable the ccstatusline terminal status bar. Default is
    NO (Enter keeps it off — opt-in). Only called from a TTY when --statusline was
    not supplied."""
    print("Optional: ccstatusline — a terminal status bar (model, git branch, "
          "context %) at the bottom of Claude Code. Wires a statusLine command "
          "and copies a default config (both no-clobber).")
    try:
        ans = input("  enable ccstatusline? [y/N]> ").strip().lower()
    except EOFError:
        ans = ""
    return ans in ("y", "yes")

def _prompt_install_mode() -> str:
    """Ask which install mode when neither --global nor --project was passed.
    Returns "global" or "project". Default (Enter/EOF) is "project" (back-compat,
    the least surprising). Only called from a TTY on a real install."""
    print("Install mode:")
    print("  [1] project  — the harness/ tree lives INSIDE this project "
          "(back-compat, default)")
    print("  [2] global   — one shared binary serves many projects via "
          "$HARNESS_BIN_ROOT (no per-project tree)")
    try:
        ans = input("  select mode [1=project / 2=global]> ").strip().lower()
    except EOFError:
        ans = ""
    return "global" if ans in ("2", "global", "g") else "project"


def _prompt_cli() -> bool:
    """Ask once whether to put the `hs-cli` launcher on PATH. Default NO (Enter
    keeps it off — opt-in). Only called from a TTY when --cli was not supplied."""
    print("Optional: hs-cli — an on-PATH launcher for harness operator verbs "
          "(doctor, list, components, migrate, version). Symlinks "
          "~/.local/bin/hs-cli at the shipped wrapper (no-clobber).")
    try:
        ans = input("  install the hs-cli launcher? [y/N]> ").strip().lower()
    except EOFError:
        ans = ""
    return ans in ("y", "yes")

def _prompt_components(optional_list, defaults=None) -> str:
    """Interactively choose which OPTIONAL components to enable (the install
    UX). Core is never asked — it is always on. Each component's default follows
    the shipped component-policy (hook-bearing components like rbac/decision-capture;
    enabling a group is an opt-in); Enter keeps that default. Returns a
    `--components` value: 'all' when every component ends up on, otherwise a CSV
    of the kept names. Only called from a TTY when --components was not supplied."""
    if not optional_list:
        return "all"
    defaults = defaults or {}
    print("Optional components — Enter keeps the shipped default "
          "(opt-in to enable). "
          "Core ships always-on and is not asked.")
    kept = []
    for name in optional_list:
        default_on = bool(defaults.get(name, False))
        hint = "Y/n" if default_on else "y/N"
        try:
            ans = input("  enable %s? [%s]> " % (name, hint)).strip().lower()
        except EOFError:
            ans = ""
        if ans == "":
            on = default_on
        else:
            on = ans in ("y", "yes", "on", "true")
        if on:
            kept.append(name)
    if len(kept) == len(optional_list):
        return "all"
    return ",".join(kept)

def _stdin_is_tty() -> bool:
    """Seam over sys.stdin.isatty() so the interactive decision is testable."""
    return sys.stdin.isatty()

def _git_user_email() -> str:
    """The invoker's git email, used only as a reviewer SUGGESTION. Attribution,
    never authentication. Empty when git or the config is absent."""
    try:
        out = subprocess.run(["git", "config", "user.email"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001 — a missing git must not abort the install
        return ""

def _load_skill_clusters(source_root):
    """The onboarding cluster map (skill-defaults.yaml `clusters`) + the recommended
    ON set (all skills minus the default-off catalog). Returns (clusters, on_set) or
    ({}, None) when the catalog is unavailable (caller falls back to the plain flow)."""
    try:
        import sys as _sys
        from pathlib import Path as _P
        sdir = str(_P(source_root) / "harness" / "scripts")
        if sdir not in _sys.path:
            _sys.path.insert(0, sdir)
        import yaml_io
        import skill_selection as ssel
        data = yaml_io.yaml_load(
            (_P(source_root) / "harness" / "data" / "skill-defaults.yaml").read_text(
                encoding="utf-8")) or {}
        clusters = data.get("clusters") or {}
        off = ssel.load_defaults(source_root)
        if not clusters or off is None:
            return {}, None
        return clusters, ssel.all_skills(source_root) - off
    except Exception:  # noqa: BLE001 — no catalog -> plain flow, never crash install
        return {}, None


def _prompt_skill_selection(group_labels, source_root=None) -> tuple:
    """Interactively choose which skills to install for the single hs plugin.

    Returns ``(skills_csv, groups_csv, add_skills)`` to feed install():
      - recommended (default) -> ``(None, None, None)`` — the default-off catalog:
                                 ~38 ON (spine floor + interview keep-list), rest stashed.
      - by cluster            -> ``(None, None, [<picked-cluster skills>])`` — the
                                 recommended baseline PLUS only the opt-in clusters
                                 (dep-closed); zero clusters resolves to the exact
                                 recommended set (the baseline is never re-dep-closed).
      - everything            -> ``("<every skill name>", None, None)`` — ship-all.

    The 13-skill spine SDLC core is never asked — it always installs. Only called
    from a TTY when neither --skills nor --skill-groups was supplied."""
    clusters, on_set = _load_skill_clusters(source_root) if source_root else ({}, None)
    if not clusters or on_set is None:
        # No default-off catalog available — fall back to the plain group/manual flow.
        return _prompt_skill_selection_plain(group_labels)
    print("Skill selection — the spine core + recommended set always installs:")
    print("  [1] recommended (~%d on, rest stashed for hs:use)   "
          "[2] + enable clusters   [3] everything" % len(on_set))
    try:
        mode = input("  choose [1]> ").strip()
    except EOFError:
        mode = ""
    if mode == "3":
        # everything = the recommended set plus every clustered (off) skill
        allc = sorted(on_set | {s for members in clusters.values() for s in members})
        return (",".join(allc), None, None)
    if mode == "2":
        # collect ONLY the opt-in cluster skills; the recommended baseline is added
        # by the resolver's add_skills path, unclosed, so 0 clusters == recommended.
        picked = set()
        print("  clusters — Enter skips (recommended set ships regardless):")
        for c in sorted(clusters):
            try:
                ans = input("    enable %s (%d skills)? [y/N]> "
                            % (c, len(clusters[c]))).strip().lower()
            except EOFError:
                ans = ""
            if ans in ("y", "yes", "on", "true"):
                picked.update(clusters[c])
        return (None, None, sorted(picked))
    return (None, None, None)  # recommended (default-off catalog)


def _prompt_skill_selection_plain(group_labels) -> tuple:
    """Legacy group/manual flow, used when the default-off catalog is unavailable."""
    print("Skill selection — the spine SDLC core always installs; pick extras:")
    print("  [1] all skills (default)   [2] by group   [3] manual (skill names)")
    try:
        mode = input("  choose [1]> ").strip()
    except EOFError:
        mode = ""
    if mode == "2":
        kept = []
        print("  groups — Enter skips (the core ships regardless):")
        for g in sorted(group_labels):
            try:
                ans = input("    include %s? [y/N]> " % g).strip().lower()
            except EOFError:
                ans = ""
            if ans in ("y", "yes", "on", "true"):
                kept.append(g)
        return (None, ",".join(kept), None)
    if mode == "3":
        try:
            csv = input("  skill names (comma-separated)> ").strip()
        except EOFError:
            csv = ""
        return (csv, None, None)
    return (None, None, None)  # all
