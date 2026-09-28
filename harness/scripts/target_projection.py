#!/usr/bin/env python3
"""Project the harness's hook registrations onto a non-Claude runtime.

`hook-dispatch.yaml` says WHAT the harness registers; `runtime-targets.yaml` says
what a given runtime can actually carry. This module is the negotiation between
them, and its whole reason to exist is that the negotiation's failure mode is
silent: a hook registered on a tool the runtime does not have never fires, and a
gate that never fires is indistinguishable from a gate that protects.

So every decision is RECORDED, not just the lossy ones, and one class of loss is
an error rather than a warning: a compliance registration that loses every atom
it matched on. `fail_open` does not exempt it — that flag governs the CRASH path
only; a fail_open compliance hook still returns BLOCK, so losing it silently
removes a real gate.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import artifact_io
import yaml_io

_ROOT = Path(__file__).resolve().parents[2]
_TARGETS = _ROOT / "harness" / "data" / "runtime-targets.yaml"
_DISPATCH = _ROOT / "harness" / "data" / "hook-dispatch.yaml"

SCHEMA = "hs-emit/1"
KINDS = ("keep", "narrow", "drop", "specialise")


class Decision:
    """One registration group's fate on one target."""

    __slots__ = ("group", "event", "matcher", "kind", "kept", "dropped_atoms",
                 "reason", "handlers", "gates")

    def __init__(self, group, event, matcher, kind, kept, dropped_atoms, reason,
                 handlers, gates=()):
        self.group = group
        self.event = event
        self.matcher = matcher
        self.kind = kind
        self.kept = kept
        self.dropped_atoms = list(dropped_atoms)
        self.reason = reason
        self.handlers = list(handlers)
        # Every compliance gate this group carries — NOT what it lost. Which of them
        # is actually lost is derived below, from this row's kind: a group that keeps
        # or narrows its matcher still fires its gates, and a ledger that calls them
        # lost teaches its reader to discount the entries that are real.
        self.gates = list(gates)

    @property
    def lost_gates(self) -> list:
        """The gates this row actually stops protecting with.

        Only a dropped group loses them: it registers and never fires. A narrowed
        group still fires on what survived — narrower, which `dropped_atoms` and the
        reason line already say, and which is a different claim from gone."""
        return list(self.gates) if self.kind == "drop" else []

    def as_record(self, target_id: str) -> dict:
        return {
            "target": target_id,
            "group": self.group,
            "event": self.event,
            "matcher": self.matcher,
            "kind": self.kind,
            "kept": self.kept,
            "dropped_atoms": self.dropped_atoms,
            "handlers": self.handlers,
            "gates": self.gates,
            "lost_gates": self.lost_gates,
            "reason": self.reason,
        }


class Projection:
    # Carries the target DECLARATION it was projected from. The writer needs the same
    # capability facts the projection used; re-reading them from disk would let the two
    # answer differently for one emit.
    __slots__ = ("target_id", "decisions", "refusals", "target")

    def __init__(self, target_id, decisions, refusals, target=None):
        self.target_id = target_id
        self.decisions = list(decisions)
        self.refusals = list(refusals)
        self.target = dict(target or {})

    @property
    def ok(self) -> bool:
        return not self.refusals


def load_targets(path: Path | str | None = None) -> dict[str, Any]:
    data = yaml_io.safe_load(Path(path or _TARGETS).read_text(encoding="utf-8")) or {}
    return data.get("targets") or {}


def load_groups(path: Path | str | None = None) -> dict[str, Any]:
    data = yaml_io.safe_load(Path(path or _DISPATCH).read_text(encoding="utf-8")) or {}
    return data.get("groups") or {}


def _split(group_key: str) -> tuple[str, str | None]:
    event, sep, matcher = group_key.partition(":")
    return event, (matcher if sep else None)


def _atom_state(atom: str, target: dict) -> str:
    if atom in (target.get("tool_atoms") or []):
        return "supported"
    if atom in (target.get("unsupported_atoms") or []):
        return "unsupported"
    return "unknown"


def _is_gate(spec: dict) -> bool:
    # fail_open is a crash posture, not an exemption — see the module docstring.
    return spec.get("class") == "compliance"


def project(groups: dict, target: dict) -> Projection:
    events = set(target.get("events") or [])
    wildcards = target.get("event_wildcard") or {}
    tid = target.get("id", "?")
    decisions: list = []
    refusals: list = []
    # A runtime with NO hook surface has not lost one gate per group — it has one
    # property. Repeating that property once per compliance group buries the section
    # where a hook-BEARING runtime's real, named losses live, and a reader who learns
    # to skim it there skims it everywhere. Measured: four of nine declared runtimes
    # have no hook file, and each was producing eight identical refusals.
    #
    # A generated bridge (render_hook_bridge) is a SECOND kind of hook surface — not
    # a translated registration file, a JS module that shells out to the same Python
    # dispatcher — so a target declaring one is not gateless even with hook_file null.
    _placement = target.get("placement") or {}
    gateless = (_placement.get("hook_file", "?") is None
                and not _placement.get("hook_bridge_file"))

    # The runtime's own spelling, resolved once. A raw comparison between the
    # harness's PascalCase group keys and a camelCase runtime's declared list reports
    # every event as absent — and the ledger then says "event PreToolUse is absent"
    # for a runtime that has it, which is a loud sentence about a wrong fact.
    for key, specs in groups.items():
        specs = specs or []
        event, matcher = _split(key)
        spelled = runtime_event_name(target, event)
        names = [s.get("name", "?") for s in specs]
        gates = [s.get("name", "?") for s in specs if _is_gate(s)]

        if spelled is None:
            event = _fallback_spelling(target, event)
            decisions.append(Decision(
                key, event, matcher, "drop", None, _atoms(matcher),
                "the target declares no %s event under any name it declares, so "
                "nothing registered on it can run there" % event, names, gates))
            if not gateless:
                _refuse(refusals, tid, key, gates, "event %s is absent" % event)
            continue
        event = spelled

        if matcher in (None, "", "*"):
            enum = wildcards.get(event)
            if enum:
                decisions.append(Decision(
                    key, event, matcher, "specialise", "|".join(enum), [],
                    "the target rejects a bare wildcard on %s and names its own "
                    "values, so `*` is expanded to %s" % (event, ", ".join(enum)),
                    names, gates))
            else:
                decisions.append(Decision(
                    key, event, matcher, "keep", matcher or "*", [],
                    "the target accepts %s unmatched, so the registration carries "
                    "over unchanged" % event, names, gates))
            continue

        # Translated BEFORE the support test, and the kept matcher is written in the
        # runtime's own words. Keeping the group while emitting our spelling produces
        # a registration the runtime installs and never matches — a gate that looks
        # present and fires for nothing, which is the failure this whole module exists
        # to refuse.
        tool_map = target.get("tool_map") or {}
        atoms = [tool_map.get(a, a) for a in _atoms(matcher)]
        kept = [a for a in atoms if _atom_state(a, target) == "supported"]
        lost = [a for a in atoms if a not in kept]

        if not lost:
            decisions.append(Decision(
                key, event, matcher, "keep", "|".join(kept), [],
                "every tool this group matches on exists on the target", names, gates))
        elif kept:
            decisions.append(Decision(
                key, event, matcher, "narrow", "|".join(kept), lost,
                "the target has %s but not %s, so the matcher is narrowed and the "
                "dropped tools go unwatched there"
                % ("|".join(kept), ", ".join(_describe(lost, target))), names, gates))
        else:
            decisions.append(Decision(
                key, event, matcher, "drop", None, lost,
                "no tool this group matches on exists on the target (%s), so the "
                "registration would be inert"
                % ", ".join(_describe(lost, target)), names, gates))
            _refuse(refusals, tid, key, gates,
                    "every matcher atom is gone (%s)" % ", ".join(_describe(lost, target)))

    # A refusal names a GATE, so it has to be true of the gate — not of one of its
    # lanes. A gate registered on two groups can lose one and keep the other; refusing
    # it then puts a false sentence in the one place this module cannot afford one.
    # The lost lane is still recorded: it is `lost_gates` on the dropped row.
    alive = {g for d in decisions if d.kind != "drop" for g in d.gates}
    if gateless:
        lost_gates = sorted({g for d in decisions for g in d.gates} - alive)
        if lost_gates:
            # ONE sentence, and it carries the COUNT: "no gates here" and "all eleven
            # of your gates are not here" land very differently on someone deciding
            # whether to install.
            # What it DOES carry is read off the same table, not asserted: one of
            # these runtimes writes no instructions file at all, and naming one it
            # never writes sends the reader looking for a file that is not there.
            carries = _and_list(
                ["skills", "agent roles"]
                + (["project instructions"]
                   if (target.get("placement") or {}).get("instructions_file")
                   else []))
            refusals = ["%s has no hook surface the harness can register on, so none of its "
                        "%d compliance gate(s) travel: %s. This install carries %s "
                        "and enforces nothing."
                        % (tid, len(lost_gates), ", ".join(lost_gates), carries)]
            return Projection(tid, decisions, refusals, target)
    refusals = [_render_refusal(*r) for r in refusals if r[1] not in alive]
    return Projection(tid, decisions, refusals, target)


def _atoms(matcher: str | None) -> list[str]:
    return [a for a in (matcher or "").split("|") if a]


def _describe(atoms: list[str], target: dict) -> list[str]:
    """Name each lost atom WITH why it was lost. `unknown` is not a synonym for
    absent: an unmeasured atom might match and might not, and the difference is
    exactly what the reader needs to decide whether to go measure it."""
    out = []
    for a in atoms:
        state = _atom_state(a, target)
        out.append("%s (%s)" % (a, "not on this runtime" if state == "unsupported"
                                else "never measured on this runtime"))
    return out


def _refuse(pending: list, target_id: str, group: str, gates: list, why: str) -> None:
    """Record a CANDIDATE refusal. Whether it survives is decided once every group has
    been projected — a gate is only refused when no group leaves it able to fire."""
    for g in gates:
        pending.append((target_id, g, group, why))


def _render_refusal(target_id: str, gate: str, group: str, why: str) -> str:
    return ("%s: compliance gate `%s` (group %s) would register and never fire on "
            "%s — %s. A gate that cannot fire reads exactly like one that protects."
            % (target_id, gate, group, target_id, why))


def write_ledger(projection: Projection, path: Path | str, target_id: str | None = None) -> Path:
    tid = target_id or projection.target_id
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for d in projection.decisions:
            fh.write(json.dumps(d.as_record(tid), ensure_ascii=False) + "\n")
    return path


def project_target(target_id: str, groups: dict | None = None,
                   targets: dict | None = None) -> Projection:
    targets = targets if targets is not None else load_targets()
    if target_id not in targets:
        raise KeyError(target_id)
    return project(groups if groups is not None else load_groups(), targets[target_id])


# ── Writing a projection out as a runnable install ────────────────────────────────
#
# Every hook the harness registers is wired the same way on Claude Code:
#
#     python3 "$CLAUDE_PROJECT_DIR"/harness/hooks/hook_dispatch.py <Event> "<matcher>"
#
# `CLAUDE_PROJECT_DIR` is set by Claude Code and by nothing else. Emitting it into
# another runtime's config yields `python3 /harness/hooks/hook_dispatch.py` — a path
# that does not exist, on a runtime that does not surface hook stderr. So the writer
# addresses the dispatcher by absolute path and a test holds that line.

_DISPATCH_REL = "harness/hooks/hook_dispatch.py"
_SURVIVES = ("keep", "narrow", "specialise")


def _argv(engine_root: Path, event: str, matcher: str | None,
          target: dict | None = None, target_id: str | None = None) -> list:
    """The dispatch invocation, as the tokens it actually is.

    Built from the ENGINE root — where the harness binary is — which is the project
    only when the project carries a copy of it. A global install serves one shared
    binary and deliberately copies no per-project tree, and addressing the project
    there names a dispatcher that is not on disk: the runtime spawns a program that
    never starts, and a gate that cannot run is indistinguishable from one that
    passed.

    `--runtime` rides along ONLY where the runtime's envelope differs from the one
    the gates read. Passing it everywhere would make the home runtime pay for a
    translation it does not need, on every one of its spawns.
    """
    script = "%s/%s" % (str(engine_root).rstrip("/"), _DISPATCH_REL)
    argv = [script, event] + ([matcher] if matcher else [])
    if target_id and (target or {}).get("payload_dialect"):
        argv += ["--runtime", target_id]
    return argv


def _command(engine_root: Path, event: str, matcher: str | None,
             target: dict | None = None, target_id: str | None = None) -> str:
    argv = _argv(engine_root, event, matcher, target, target_id)
    return " ".join(['python3 "%s"' % argv[0]] + [
        a if a.startswith("--") else '"%s"' % a for a in argv[1:]])


def bridge_routing_table(projection: Projection, engine_root: Path, target: dict,
                         target_id: str, event: str = "PreToolUse") -> dict:
    """Runtime-native tool name -> [argv, ...] for every surviving compliance gate.

    Derived from `projection.decisions` — the SAME rows render_caveats and
    render_placement read — so a bridge generated from this can never disagree with
    the projection about which gate lives. Only groups that carry a real compliance
    gate are routed (`d.gates`): a tool with no compliance registration at all would
    otherwise spawn the dispatcher on every call for nothing to check.

    `d.kept` already holds the SURVIVING atoms in the runtime's own vocabulary (the
    projection's tool_map ran before the support test), so no second translation
    happens here — reading it twice with two different tables is how a bridge and
    its projection drift apart.
    """
    spelled = runtime_event_name(target, event) or event
    table: dict = {}
    for d in projection.decisions:
        if d.kind not in _SURVIVES or d.event != spelled or not d.kept or not d.gates:
            continue
        # The dispatcher's own registry keys on OUR home event name ("PreToolUse"),
        # never the runtime's spelling — `event` here, not the translated `d.event`.
        argv = _argv(engine_root, event, d.matcher, target, target_id)
        # Two OUR atoms can alias to the SAME native tool (tool_map: both `Edit` and
        # `MultiEdit` -> pi's one `edit`), so `kept` can repeat a name. dict.fromkeys
        # dedupes while keeping first-seen order — a route listed twice would spawn
        # the dispatcher twice for one tool call, for the identical group.
        for atom in dict.fromkeys(d.kept.split("|")):
            existing = table.setdefault(atom, [])
            if argv not in existing:
                existing.append(argv)
    return table


def render_hook_bridge(projection: Projection, engine_root: Path, target: dict,
                       target_id: str) -> str:
    """A generated JS/TS extension module bridging a runtime whose hook surface is a
    script factory (not a translated config file) to the SAME Python dispatcher every
    hook_file target already calls.

    Built for the one measured runtime whose extension API documents an awaited
    `tool_call` handler that can return `{block, reason}` (see caveats.
    hook_surface_is_a_module) — general over the routing TABLE (derived, never
    hand-listed) even though the module shape below is written for that one API.
    A second runtime needing this would extend the template, not fork it.

    Spawns via `node:child_process` directly, NOT the runtime's own `pi.exec`
    helper — measured (pi 0.84.3, dist/core/exec.js) to hardcode
    `stdio: ["ignore", "pipe", "pipe"]` with no stdin/env passthrough in its
    options, so a payload handed to `pi.exec` never reaches the child. Extensions
    are plain Node, not sandboxed away from its builtins — a third-party hooks
    extension studied for this runtime imports `node:child_process`, `node:fs`
    and `node:path` directly and pipes its own hook payload the same way
    (`child.stdin.end(encodedPayload)`), so this is
    the established, reachable path for the exact same constraint, not a guess.

    The dispatcher's own home-format contract (exit 2 + stderr "BLOCKED: reason", or
    exit 0 + a `hookSpecificOutput.permissionDecision` JSON deny) is read directly —
    this bridge builds the payload in that SAME home shape itself, so no
    `payload_dialect`/`--runtime` translation is needed on the Python side at all.
    """
    table = bridge_routing_table(projection, engine_root, target, target_id)
    tool_map = target.get("tool_map") or {}
    reverse_map = {v: k for k, v in tool_map.items()}

    def _js_str(value: str) -> str:
        return json.dumps(value)

    def _argv_js(argv: list) -> str:
        return "[%s]" % ", ".join(_js_str(a) for a in argv)

    routes_js = ",\n  ".join(
        "%s: [%s]" % (_js_str(tool), ", ".join(_argv_js(a) for a in argv_list))
        for tool, argv_list in sorted(table.items()))
    tool_name_js = ",\n  ".join(
        "%s: %s" % (_js_str(native), _js_str(reverse_map.get(native, native)))
        for native in sorted(table))

    return '''// GENERATED by harness/scripts/target_projection.py (render_hook_bridge). Do not
// hand-edit — a re-install overwrites this file. See this runtime's declared
// caveat `hook_surface_is_a_module` for the measurement this bridge is built on.
//
// This module IS the runtime's own extension format: a default-exported factory
// registering `pi.on("tool_call", ...)`. Inside the handler it shells out to the
// harness's own Python hook dispatcher via a direct `node:child_process.spawn`
// (not `pi.exec`, which cannot pipe a payload to the child's stdin) and maps the
// dispatcher's verdict onto the `{block, reason}` shape the runtime reads to
// actually stop a tool call — the runtime never sees Python directly, only this
// JS shim's verdict.
import { spawn } from "node:child_process";

const ROUTES = {
  %s
};

const TOOL_NAME = {
  %s
};

function runDispatcher(argv, payload) {
  return new Promise((resolve) => {
    const [command, ...args] = argv;
    const child = spawn(command, args, { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.stderr.on("data", (d) => { stderr += d.toString(); });
    child.on("close", (code) => resolve({ stdout, stderr, code: code ?? 0 }));
    child.on("error", () => resolve({ stdout, stderr, code: 1 }));
    child.stdin.on("error", () => { /* EPIPE on an early-exiting child */ });
    child.stdin.end(payload);
  });
}

export default function (pi) {
  pi.on("tool_call", async (event, ctx) => {
    const routes = ROUTES[event.toolName];
    if (!routes || routes.length === 0) return undefined;
    const toolName = TOOL_NAME[event.toolName] || event.toolName;
    const payload = JSON.stringify({
      hook_event_name: "PreToolUse",
      tool_name: toolName,
      tool_input: event.input,
      session_id: (ctx && ctx.sessionManager && ctx.sessionManager.sessionId) || "",
    });
    for (const argv of routes) {
      const result = await runDispatcher(["python3", ...argv], payload);
      if (result.code === 2) {
        const m = /BLOCKED: (.*)/.exec(result.stderr || "");
        return { block: true, reason: m ? m[1] : "blocked by the harness dispatcher" };
      }
      if (result.code === 0 && result.stdout) {
        try {
          const out = JSON.parse(result.stdout);
          const spec = out.hookSpecificOutput;
          if (spec && spec.permissionDecision === "deny") {
            return { block: true, reason: spec.permissionDecisionReason };
          }
        } catch (_e) {
          // not JSON — a bare continue write, nothing to block on
        }
      }
    }
    return undefined;
  });
}
''' % (routes_js, tool_name_js)


def _fallback_spelling(target: dict, event: str) -> str:
    """What the runtime WOULD have called it, for the sentence that says it has none.

    A drop reason naming our PascalCase spelling to a camelCase runtime is a loud
    sentence about a name that runtime never uses, so the reader checks for the wrong
    string in their own config.
    """
    fmt = target.get("hook_format") or {}
    if (fmt.get("event_case") or "pascal") == "camel":
        return event[0].lower() + event[1:]
    return event


def runtime_event_name(target: dict, event: str) -> str | None:
    """This runtime's own spelling of one of OUR event names, or None if it has none.

    Two things can differ and both are declared: the CASE, which most runtimes vary,
    and the NAME, which one of them does. The rename is checked first — measured, a
    runtime that spells the prompt-submit moment its own way had the whole lane
    dropped with the reason "the target declares no userPromptSubmit event", which
    reads like a wall and is a rename.

    One function because there were two: the projector re-cased the name to decide
    what to drop and the installer re-cased it again to decide what to write, so a
    rename taught to one of them would still have been absent from the other.
    """
    fmt = target.get("hook_format") or {}
    renamed = (fmt.get("event_map") or {}).get(event)
    if renamed:
        want = renamed
    elif (fmt.get("event_case") or "pascal") == "camel":
        want = event[0].lower() + event[1:]
    else:
        want = event
    return want if want in (target.get("events") or []) else None


def _hook_entry(target: dict, engine_root: Path, event: str, matcher, *,
                blocking: bool, target_id: str | None = None) -> dict:
    """One registration, in the shape THIS runtime parses.

    Every dimension comes from the runtime's declared `hook_format`. Writing one
    shape for all of them is the worst failure this module has: the file is on disk,
    the install reports the gates as carried, and nothing runs — which is
    indistinguishable from protection until it matters.
    """
    fmt = target.get("hook_format") or {}
    cmd = _command(engine_root, event, matcher, target, target_id)
    inner: dict[str, Any] = {"type": "command", "command": cmd}
    if (fmt.get("command_form") or "string") == "argv":
        argv = _argv(engine_root, event, matcher, target, target_id)
        inner = {"id": "%s%s" % (event, ":%s" % matcher if matcher else ""),
                 "command": "python3", "args": argv}
    win = fmt.get("windows_variant")
    if win:
        # Measured: one runtime reads a SEPARATE key for the Windows command. Without
        # it a `python3 …` line is registered on a box that has no `python3`, so the
        # gate exists and cannot run.
        inner[win] = cmd.replace('python3 "', 'python "', 1)
    fail_key = fmt.get("failure_mode_key")
    if fail_key:
        # A compliance gate that fails open is a gate that stops protecting exactly
        # when it breaks. The runtime has a field for this; posture goes in it.
        inner[fail_key] = "closed" if blocking else "open"

    entry = {}
    if matcher:
        entry["matcher"] = ([matcher] if (fmt.get("matcher_form") == "array")
                            else matcher)
    # An absent matcher means "every call", and the runtimes measured say that by
    # OMITTING the key. Writing `"matcher": null` says something else to a strict
    # parser, and what it says is "match nothing".
    if (fmt.get("nesting") or "grouped") == "flat":
        entry.update(inner)
    else:
        entry["hooks"] = [inner]
    return entry


_SKILLS_REL = "harness/plugins/hs/skills"


def _declared_name(skill_md: Path, fallback: str) -> str:
    """The name the skill declares — which is what the runtime lists it under."""
    text = skill_md.read_text(encoding="utf-8")
    if text.startswith("---"):
        for line in text.split("---", 2)[1].split(chr(10)):
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
    return fallback


def _skill_dir_name(declared: str, decl: dict, fallback: str) -> str:
    """The directory a skill lands in.

    Derived from the DECLARED name, not from the source directory: two runtimes
    require the frontmatter `name:` to match the directory and take no colon in
    either, and our source pairs a `plan/` directory with a `hs:plan` name. Renaming
    one without the other is exactly the shape their own loader rejects, so both
    come from here.
    """
    if decl.get("name_rewrite") == "colon_to_dash":
        return (declared or fallback).replace(":", "-")
    return fallback


def _project_skill_file(path: Path, decl: dict, dir_name: str) -> None:
    """Apply this runtime's declared frontmatter rewrites to one SKILL.md.

    Only what the table declares, and only in the FRONTMATTER: the body is prose
    written for a reader, and rewriting prose is how a port starts inventing. A
    runtime that declares nothing gets a byte-identical copy — measured, one of them
    loads a skill verbatim with the colon in its name, and rewriting there would
    break every cross-reference in every other body while fixing nothing.
    """
    if not decl:
        return
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return
    _, fm, body = text.split("---", 2)
    lines = fm.split(chr(10))
    out = []
    dropped = set(decl.get("drop_keys") or [])
    renamed = dict(decl.get("key_rewrite") or {})
    for line in lines:
        key = line.split(":", 1)[0].strip() if ":" in line else None
        if key and key in dropped:
            continue
        if key and key in renamed:
            line = line.replace("%s:" % key, "%s:" % renamed[key], 1)
            key = renamed[key]
        if key == "name" and decl.get("name_rewrite") == "colon_to_dash":
            line = "name: %s" % dir_name
        out.append(line)
    notice = decl.get("notice")
    if notice:
        # Prepended to the BODY, not the frontmatter: a skill file read on its own —
        # copied out of the export by hand, which is the whole point of that target —
        # otherwise carries no sign that it was rewritten for a runtime it was not
        # written for.
        body = "%s> %s%s%s" % (chr(10), (chr(10) + "> ").join(
            " ".join(notice.split()).split(". ")), chr(10), body)
    path.write_text("---%s---%s" % (chr(10).join(out), body), encoding="utf-8")


def _copy_skills(names, out_dir: Path, target: dict | None = None,
                 src_root=None) -> list[str]:
    """Copy each named skill directory whole, in the shape this runtime loads.

    Whole, not just its SKILL.md: a body that orders a self-check against files
    beside it becomes an order pointing at nothing when only the body travels.

    What gets rewritten on the way is DECLARED, never inferred. Measured on one
    runtime: a skill is listed to the model by its frontmatter `name:` verbatim,
    `hs:` prefix included, so renaming there would break every cross-skill reference
    in every other body while fixing nothing. Two others cannot take that colon at
    all, and one reads a different spelling of the key that says when to invoke a
    skill — a line that is simply invisible there under our spelling.
    """
    decl = ((target or {}).get("skills")) or {}
    src_root = Path(src_root) if src_root else _ROOT / _SKILLS_REL
    shipped = []
    for name in names:
        src = src_root / name
        if not (src / "SKILL.md").is_file():
            continue
        dir_name = _skill_dir_name(_declared_name(src / "SKILL.md", name), decl, name)
        dest = out_dir / "skills" / dir_name
        artifact_io.copy_tree(src, dest)
        _project_skill_file(dest / "SKILL.md", decl, dir_name)
        shipped.append(dir_name)
    return shipped


_AGENTS_REL = "harness/plugins/hs/agents"


def _agent_source(name: str):
    """The agent's declarations and its body, with the frontmatter REMOVED.

    Removed on purpose. The upstream emitter embeds the whole source file, tool list
    and all, so the emitted prose advertises a restriction the target does not
    enforce — a cage that is only a sentence.
    """
    src = _ROOT / _AGENTS_REL / ("%s.md" % name)
    if not src.is_file():
        raise ValueError(
            "no such agent: %s (looked in %s). Emitting a role for an agent that does "
            "not exist would ship a name nothing backs." % (name, _AGENTS_REL))
    parts = src.read_text(encoding="utf-8").split("---", 2)
    if len(parts) < 3:
        raise ValueError("agent %s has no frontmatter to read its declarations from" % name)
    fm, body = parts[1], parts[2]
    out = {}
    for key in ("name", "description", "model", "effort", "tools"):
        m = re.search(r"^%s:[ \t]*(.+?)[ \t]*$" % key, fm, re.M)
        if m:
            out[key] = m.group(1).strip().strip("'").strip('"')
    if out.get("description", "").startswith(">"):
        out.pop("description")
    if not out.get("description"):
        m = re.search(r"^description:[ \t]*>-?[ \t]*\n((?:[ \t]+.+\n)+)", fm, re.M)
        if m:
            out["description"] = " ".join(l.strip() for l in m.group(1).splitlines())
    return out, body.strip()


def _toml_basic(value: str) -> str:
    """A TOML basic string. Prose goes in a literal block instead of through here."""
    v = value.replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
    return '"%s"' % " ".join(v.split())



_RULES_REL = "harness/rules"


def _copy_rules(out_dir: Path, target: dict) -> list:
    """The shared rule layer, into whatever directory this runtime reads.

    The rules are where this harness keeps the conventions a skill body deliberately
    does NOT restate. Shipping skills without them delivers bodies whose every pointer
    resolves to nothing, and the model reads the absence as "there was no convention".

    Content travels unchanged; only the EXTENSION varies, measured per runtime.
    """
    rel = (target.get("placement") or {}).get("rules_dir")
    if not rel:
        return []
    ext = (target.get("rules") or {}).get("extension", "md")
    dest = out_dir / Path(rel).name
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for src in sorted((_ROOT / _RULES_REL).glob("*.md")):
        (dest / ("%s.%s" % (src.stem, ext))).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(src.stem)
    return written


# The harness's own block inside a runtime's instructions file. Distinct from the
# CLAUDE.md onboarding markers: nothing routes a runtime at CLAUDE.md today, and
# distinct markers keep that a decision rather than a coincidence — shared markers
# would make each writer replace the other's block the moment one file served both.
INSTRUCTIONS_BEGIN = ("<!-- >>> harness instructions (generated; edits between "
                      "markers are overwritten on reinstall) >>> -->")
INSTRUCTIONS_END = "<!-- <<< harness instructions <<< -->"


def _write_instructions_block(out_dir: Path, target: dict, project_root: Path,
                              rule_names) -> str | None:
    """Write everything the harness contributes to the runtime's instructions file,
    as ONE marker-wrapped block.

    Markers rather than a whole file: the installer splices this into a file the user
    may already own, and prose outside the markers is theirs. Measured before that was
    true — an install for `omp` replaced a project's hand-written AGENTS.md outright.

    The rules ride inside the block only where the runtime's table says that runtime
    reads them there; everywhere else the rules directory is what it reads, and a
    second copy inside the instructions file is a copy that drifts.
    """
    name = (target.get("placement") or {}).get("instructions_file")
    if not name:
        return None
    src = Path(project_root) / _INSTRUCTIONS_SRC
    inline = bool((target.get("instructions_merge") or {}).get("rules_inline")) \
        and bool(rule_names)
    body = [INSTRUCTIONS_BEGIN, ""]
    if src.is_file():
        # A pointer, not a copy: two files carrying the same instructions drift, and
        # the drift is silent because both still read as authoritative.
        body += ["# Project instructions", "",
                 "The instructions for this project are in `%s` — read that file."
                 % _INSTRUCTIONS_SRC, ""]
    elif not inline:
        return None  # nothing to point at and nothing to inline
    for stem in rule_names if inline else []:
        body.append((_ROOT / _RULES_REL / ("%s.md" % stem))
                    .read_text(encoding="utf-8").rstrip())
        body.append("")
    body.append(INSTRUCTIONS_END)
    (out_dir / name).write_text(chr(10).join(body) + chr(10), encoding="utf-8")
    return name


def _write_agent_roles(names, out_dir: Path, decl: dict) -> list:
    """One role file per agent; returns (name, tools) for the operator notes.

    Every required key is written or the agent is refused. The target DROPS an
    incomplete role with a WARNING rather than an error, so a missing key is a silent
    loss — the failure mode this module exists to refuse.
    """
    names = list(names)
    if not names:
        return []
    if decl.get("inert_sidecar"):
        # Preserved, labelled, and deliberately NOT in the live directory. Dropping
        # them loses the material a human needs to port by hand; writing them live
        # reports an install this runtime does not perform. The label is what keeps
        # the same bytes from reading as the second thing.
        role_dir = decl.get("role_dir") or "harness-sidecar/agents"
        required = tuple(decl.get("required_keys") or ("name", "description"))
        written = _write_markdown_roles(names, out_dir, decl, role_dir, required)
        (out_dir / role_dir).mkdir(parents=True, exist_ok=True)
        (out_dir / role_dir / "INERT.md").write_text(
            "# These roles are inert on this runtime\n\n"
            "Measured: this runtime copies agent files and activates none of them. "
            "They are here so a human can port one by hand — nothing loads them, and "
            "no agent behaviour in this install comes from them.\n\n"
            "Anything relying on an agent's tool allowlist or model bound is "
            "unenforced here.\n", encoding="utf-8")
        return written
    if not decl.get("named_registry"):
        raise ValueError(
            "this target declares no named agent registry, so roles written here would "
            "sit in a directory nothing reads. Emit without agents, or correct the "
            "declaration if the registry was measured on an EMPTY config (the parameter "
            "that names a role only appears once one valid role exists)")
    effort_key = decl.get("effort_key") or "model_reasoning_effort"
    tier_map = decl.get("model_tier_map") or {}
    role_dir = decl.get("role_dir") or "agents"
    required = tuple(decl.get("required_keys") or ())
    if not required:
        raise ValueError(
            "this target declares a named registry but no required_keys, so nothing "
            "says which keys a role must carry and an incomplete role would ship")
    role_format = decl.get("role_format")
    if role_format not in ("toml", "md"):
        raise ValueError(
            "this target declares a named registry but no role_format, so the writer "
            "would have to guess between TOML and Markdown — and a role in the wrong "
            "format is a file the runtime skips while the install reports it delivered")
    if role_format == "md":
        return _write_markdown_roles(names, out_dir, decl, role_dir, required)
    fence = chr(39) * 3
    written = []
    for name in names:
        fm, body = _agent_source(name)
        desc = (fm.get("description") or "").strip()
        if not desc or not body:
            raise ValueError(
                "agent %s has no description or no body; the target would drop the "
                "role with a warning and nothing would say so" % name)
        lines = ["name = " + _toml_basic(name),
                 "description = " + _toml_basic(desc)]
        # Only a tier the declaration actually maps is emitted. An unmapped tier stays
        # unmapped: a guess would read as the model bound having been honoured.
        mapped = tier_map.get(fm.get("model"))
        if mapped:
            lines.append("model = " + _toml_basic(mapped))
        if fm.get("effort"):
            lines.append(effort_key + " = " + _toml_basic(fm["effort"]))
        if fence in body:
            raise ValueError("agent %s body carries a TOML literal delimiter" % name)
        lines.append("developer_instructions = " + fence + chr(10) + body + chr(10) + fence)
        # Checked against the DECLARATION, not against this function's own literals: a
        # target that later requires a fourth key must fail here, not ship 28 roles the
        # runtime drops one warning at a time.
        present = {ln.split(" = ", 1)[0] for ln in lines}
        missing = [k for k in required if k not in present]
        if missing:
            raise ValueError(
                "agent %s would be written without %s, which this target requires; it "
                "drops such a role with a warning and exit 0, so nothing downstream "
                "would say the role is gone" % (name, ", ".join(missing)))
        (out_dir / role_dir).mkdir(parents=True, exist_ok=True)
        (out_dir / role_dir / ("%s.toml" % name)).write_text(
            chr(10).join(lines) + chr(10), encoding="utf-8")
        written.append((name, fm.get("tools")))
    return written



def _write_markdown_roles(names, out_dir: Path, decl: dict, role_dir: str,
                          required) -> list:
    """Markdown-with-frontmatter roles, carrying only the keys the runtime reads.

    Six of the eight measured runtimes store roles this way, and each keeps a
    different set of fields. Two rules make the difference safe rather than lossy:

      A key the runtime does not read is DROPPED, not written and ignored. A `tools:`
      line on a runtime with no allowlist reads as a cage while nothing enforces it,
      and that is worse than no line at all — which is why the dropped allowlist is
      returned to the caller and lands in the operator notes.

      A model tier is emitted only where the declaration MAPS it. `passthrough` keeps
      the source value for the one runtime measured to accept it verbatim; a tier with
      no mapping is left out, because inventing a name the runtime never had reads as
      the bound having been honoured.
    """
    import yaml_io as _yaml

    keep = list(decl.get("keep_keys") or ("name", "description"))
    tier_map = decl.get("model_tier_map")
    tool_map = decl.get("tool_map") or {}
    allowed_models = decl.get("model_values")
    written = []
    for name in names:
        fm, body = _agent_source(name)
        desc = (fm.get("description") or "").strip()
        if not desc or not body:
            raise ValueError(
                "agent %s has no description or no body; the target would drop the "
                "role with a warning and nothing would say so" % name)
        out_fm = {"name": name, "description": " ".join(desc.split())}
        if "memory" in keep and fm.get("memory"):
            out_fm["memory"] = fm["memory"]
        if "model" in keep and fm.get("model"):
            src = fm["model"]
            if tier_map == "passthrough":
                out_fm["model"] = src
            elif isinstance(tier_map, dict) and tier_map.get(src):
                out_fm["model"] = tier_map[src]
            elif allowed_models and src in allowed_models:
                out_fm["model"] = src
        source_tools = fm.get("tools")
        if "tools" in keep and source_tools:
            if tool_map:
                mapped: list = []
                unmapped: list = []
                for tool in [x.strip() for x in str(source_tools).split(",") if x.strip()]:
                    (mapped if tool in tool_map else unmapped).append(
                        tool_map.get(tool, tool))
                # De-duplicated: two source tools can map onto one primitive, and a
                # repeated entry is a list the runtime reads twice.
                seen, ordered = set(), []
                for tool in mapped:
                    if tool not in seen:
                        seen.add(tool)
                        ordered.append(tool)
                if ordered:
                    out_fm["tools"] = ", ".join(ordered)
            else:
                out_fm["tools"] = source_tools
        missing = [k for k in required if k not in out_fm]
        if missing:
            raise ValueError(
                "agent %s would be written without %s, which this target requires"
                % (name, ", ".join(missing)))
        text = ("---" + chr(10)
                + _yaml.safe_dump(out_fm, sort_keys=False)
                + "---" + chr(10) + chr(10) + body.rstrip() + chr(10))
        (out_dir / role_dir).mkdir(parents=True, exist_ok=True)
        (out_dir / role_dir / ("%s.md" % name)).write_text(text, encoding="utf-8")
        # The SOURCE allowlist travels back regardless of whether it was written, so
        # the notes can say the cage did not travel for the runtimes that drop it.
        written.append((name, source_tools))
    return written

def write_install(projection: Projection, out_dir: Path | str, target_id: str,
                  project_root: Path | str, skills=None, agents=None,
                  engine_root: Path | str | None = None) -> Path:
    """Write hooks.json + the degradation ledger + operator notes into out_dir.

    `skills` names the skill directories to ship alongside. Only what is named
    travels: listing a skill the install does not carry tells the model about a
    capability it does not have.

    `project_root` and `engine_root` are the same directory for a project install and
    different ones for a global install, which is why they are two parameters. The
    instructions pointer belongs to the PROJECT — it is the user's file — and the
    hook command belongs to wherever the binary actually is.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    project_root = Path(project_root)
    engine_root = Path(engine_root) if engine_root else project_root

    target = projection.target or {}
    hooks: dict[str, list] = {}
    for d in projection.decisions:
        if d.kind not in _SURVIVES:
            continue
        matcher = d.kept if d.matcher not in (None, "", "*") else None
        hooks.setdefault(d.event, []).append(
            _hook_entry(target, engine_root, d.event, matcher,
                        blocking=bool(d.gates), target_id=target_id))

    # A runtime with no hook surface gets NO hooks file. An empty one is a file that
    # goes nowhere, and its presence is what a reader checks to see whether gates are
    # installed — so writing it answers that question wrongly.
    _placement = target.get("placement") or {}
    bridge_rel = _placement.get("hook_bridge_file")
    gateless = _placement.get("hook_file", "?") is None and not bridge_rel
    # A bridge target's hook surface is the generated module below, never a JSON
    # file — writing hooks.json there too would be a second, unread registration.
    if not gateless and not bridge_rel:
        blob = {"hooks": hooks}
        version = (target.get("hook_format") or {}).get("file_version")
        if version is not None:
            # Declared per runtime: two of the measured files carry a schema version
            # and the rest carry none, and writing one where none belongs is a key
            # the parser was not told to expect.
            blob = {"version": version, "hooks": hooks}
        (out_dir / "hooks.json").write_text(
            json.dumps(blob, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    if bridge_rel:
        bridge_path = out_dir / bridge_rel
        bridge_path.parent.mkdir(parents=True, exist_ok=True)
        bridge_path.write_text(
            render_hook_bridge(projection, engine_root, target, target_id),
            encoding="utf-8")
    write_ledger(projection, out_dir / "degradation-ledger.jsonl", target_id=target_id)
    shipped = _copy_skills(skills or [], out_dir, target)
    decl = target.get("agents") or {}
    roles = _write_agent_roles(agents or [], out_dir, decl)
    rule_names = _copy_rules(out_dir, target)
    # Only where the runtime reads one. A file written for a runtime that reads none
    # sits in the tree looking authoritative while nothing loads it.
    instructions = _write_instructions_block(out_dir, target, project_root, rule_names)
    (out_dir / "INSTALL.md").write_text(
        _notes(projection, target_id, shipped, instructions, roles,
               target.get("unhooked_atoms"), gateless=gateless,
               trust_model=(target.get("caveats") or {}).get("hook_trust"),
               allowlist_travels=bool(decl.get("tool_allowlist")),
               target=target),
        encoding="utf-8")
    return out_dir


_INSTRUCTIONS_SRC = "CLAUDE.md"



# The measured facts in the table reach a human ONLY here. Anything declared and
# unrendered is a measurement that was taken and thrown away — which is how nine of
# the ten declared caveats spent their life in a data file nobody printed.
_PLACEMENT_LABEL = {
    "hook_file": "hook registration",
    "skills_dir": "skills",
    "skills_dir_secondary": "skills (second copy — this runtime reads both)",
    "agents_dir": "agent roles",
    "rules_dir": "rules",
    "instructions_file": "project instructions",
}


def _and_list(items) -> str:
    items = list(items)
    if len(items) < 2:
        return items[0] if items else ""
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def render_caveats(target: dict) -> str:
    """Every caveat this runtime declares, keyed by nothing but its own name.

    Deliberately not a fixed list of today's keys: a caveat added to the table next
    week is a measurement someone took, and a renderer that knows only the current
    keys drops it silently.
    """
    caveats = target.get("caveats") or {}
    if not caveats:
        return ""
    # A key ending in _carried_unverified is the one deliberate exception to "we
    # measured this ourselves": naming it in the key, not just the prose, means a
    # future caveat inherits the softened header only by explicitly saying so.
    any_carried = any(key.endswith("_carried_unverified") for key in caveats)
    header = ("Each line was observed on this runtime's own emitted tree, unless it "
              "says otherwise below." if any_carried else
              "Each line was observed on this runtime's own emitted tree, not "
              "inferred from another one.")
    out = ["## What was measured about this runtime", "", header, ""]
    for key in sorted(caveats):
        out.append("- **%s** — %s" % (key.replace("_", " "),
                                      " ".join(str(caveats[key]).split())))
    out.append("")
    return chr(10).join(out)


def render_placement(target: dict) -> str:
    """Where each kind belongs on this runtime, and what it does not read at all.

    An operator porting by hand has the emitted tree and nothing else; a directory
    the runtime reads that the tree does not name is a directory they will not create.
    """
    place = target.get("placement") or {}
    rows = [(_PLACEMENT_LABEL.get(k, k.replace("_", " ")), v)
            for k, v in place.items() if k != "scope" and v]
    if not rows:
        return ""
    out = ["## Where this runtime reads each kind", "",
           "Paths are the runtime's own, measured from its emitted tree. Scope: "
           "**%s**." % (place.get("scope") or "unstated"), ""]
    for label, value in rows:
        out.append("- %s — `%s`" % (label, value))
    absent = [_PLACEMENT_LABEL[k] for k in _PLACEMENT_LABEL if not place.get(k)]
    if absent:
        out.append("")
        out.append(
            "Reads none of: %s. Nothing of that kind is in this tree, because a file "
            "written where nothing loads it reads as installed. Not dropped either: "
            "the harness tree the install copies carries every one of them under "
            "`harness/`, and the skill bodies point at them there. A second copy "
            "here would be a copy that drifts from the one the gates read."
            % ", ".join(sorted(absent)))
    out.append("")
    return chr(10).join(out)


def render_model_rule(target: dict) -> str:
    """Which `model:` values survive here, for a runtime that filters them.

    Measured per runtime rather than assumed: one runtime keeps the key and accepts
    exactly one value, and writing a Claude tier there reads as a bound honoured by a
    name the runtime never knew.
    """
    decl = target.get("agents") or {}
    allowed = decl.get("model_values")
    if not allowed:
        return ""
    return chr(10).join([
        "## The model line on an agent role", "",
        "This runtime reads `model:` and accepts %s. Every other value — including "
        "each of the harness's own model tiers — is stripped, so a role that named "
        "one arrives with no model line and the runtime applies its default. Choose "
        "the model when you launch the agent, not in the role file."
        % ", ".join("`%s`" % v for v in allowed), ""])


def render_extra_events(target: dict, carried=()) -> str:
    """Hook events this runtime raises that nothing here registers on.

    Measured, and deliberately not silent. An operator reading a coverage report sees
    the events the harness registered and has no way to tell an event this runtime
    does not HAVE from one it has and nobody used — and those two lead to opposite
    decisions. The first is a wall; the second is a gap someone can close.

    Two sources, one answer. `extra_events` holds what a runtime supports and this
    table does not otherwise list; the ordinary `events` list holds what it supports
    and we DO ask about — and one of those was going unregistered anyway. Subtracting
    what the projection actually carried covers both, and means no second hand-kept
    list to drift from the first.
    """
    carried = set(carried or ())
    extra = [e for e in list(target.get("events") or [])
             + list(target.get("extra_events") or []) if e not in carried]
    if not extra:
        return ""
    return chr(10).join([
        "## Events this runtime raises that nothing here uses", "",
        "Measured on the runtime, not inferred: it also raises %s. The harness "
        "registers on none of them, so nothing in this install runs at those points. "
        "This is unused capability, not a limit — a later registration has somewhere "
        "to go." % _and_list(["`%s`" % e for e in extra]), ""])


def foreign_block_marker(text: str) -> str | None:
    """The opening marker of a block in this file that belongs to someone else.

    One measured runtime keeps its project instructions in a file other tools also
    write into, each side wrapping its own block in a marker comment. Which tool is
    not the point and naming one would only cover that one: any `<!-- NAME:START`
    comment that is not ours means the file has a second owner, and the operator who
    does not know that will hand-edit one block and blame the wrong install.

    Returns the marker as it appears in THEIR file, so the warning quotes the thing
    the reader will actually search for.
    """
    for m in re.finditer(r"<!--\s*([A-Z][A-Z0-9_.-]{2,}(?::[A-Za-z0-9_.-]+)*)\s*-->",
                         text or ""):
        token = m.group(1)
        if ":START" not in token.upper():
            continue
        if token in INSTRUCTIONS_BEGIN or INSTRUCTIONS_BEGIN in m.group(0):
            continue
        return m.group(0)
    return None


def _notes(projection: Projection, target_id: str, shipped=(),
           instructions=None, roles=(), unhooked=None, gateless=False,
           trust_model=None, allowlist_travels=False, target=None) -> str:
    lost = [d for d in projection.decisions if d.kind not in _SURVIVES]
    kept = [d for d in projection.decisions if d.kind in _SURVIVES]
    out = ["# %s install — what is here and what is not" % target_id, ""]
    out.append("%d registration group(s) carried over; %d did not." % (len(kept), len(lost)))
    out.append("")
    if unhooked:
        # A tool that executes while no hook fires is not a gap in the gates — it is a
        # gap UNDER them. The gate on the neighbouring tool still passes, so the install
        # reads as covered. Say so before anything else claims coverage.
        alive = sorted({g for d in projection.decisions
                        if d.kind in _SURVIVES for g in d.gates})
        out.append("## Tools that execute here without firing a hook")
        out.append("")
        out.append("Nothing below can be gated on this runtime: it runs and no hook "
                   "event is raised for it. This is not something the harness can "
                   "close — there is no event to register on.")
        out.append("")
        for atom in sorted(unhooked):
            out.append("- `%s` — %s" % (atom, unhooked[atom]))
        out.append("")
        if alive:
            out.append("Consequence for the gates that DID survive here (%s): each one "
                       "reads the tool call it is registered on, so anything reaching "
                       "the runtime through the tools above passes them unseen. Treat "
                       "their coverage as conditional on the model not using those "
                       "tools, which is an assumption, not an enforcement."
                       % ", ".join("`%s`" % g for g in alive))
            out.append("")
    # Written per runtime rather than once. The paragraph below is one runtime's
    # hook TRUST model, and printing it for a runtime with no hooks describes a step
    # that does not exist there — which is worse than saying nothing, because a
    # reader who performs it believes the install is finished.
    if not gateless:
        out.append("## Before this install does anything")
        out.append("")
        if trust_model:
            out.append(trust_model)
        else:
            out.append(
                "Writing the hooks file does not install the hooks. Check how this "
                "runtime admits a hook — several require an explicit grant before one "
                "runs — and treat the install as unfinished until you have.")
        out.append("")
    else:
        out.append("## This runtime has no hook surface")
        out.append("")
        carried = ["skills", "agent roles"]
        if instructions:
            carried.append("project instructions")
        out.append(
            "Nothing here enforces anything. The install carries %s; every compliance "
            "gate the harness runs on its home runtime is absent, because there is no "
            "event to register one on. Read the list further down before relying on "
            "this install for anything the gates normally catch."
            % _and_list(carried))
        out.append("")
    if instructions:
        out.append("## Project instructions")
        out.append("")
        out.append("`%s` points at `%s` rather than copying it, so the two cannot "
                   "drift apart." % (instructions, _INSTRUCTIONS_SRC))
        out.append("")
    if shipped:
        out.append("## Skills shipped with this install")
        out.append("")
        out.append("Loaded verbatim by the runtime and listed to the model under the "
                   "name each one declares:")
        out.append("")
        for name in shipped:
            out.append("- `%s`" % name)
        out.append("")
    if roles:
        # Which of these two paragraphs is true is a property of the RUNTIME, and
        # printing the wrong one is worse in both directions: telling a reader a cage
        # was lost that travelled makes them add controls they already have, and
        # telling them it travelled when it did not leaves a role that reads as caged
        # while nothing enforces the cage.
        if allowlist_travels:
            out.append("## Agent roles shipped")
            out.append("")
            out.append("Each agent's prose, description and per-agent TOOL allowlist "
                       "travel — this runtime's role schema has a field for the "
                       "allowlist and the emitter fills it.")
            out.append("")
            for name, tools in roles:
                out.append("- `%s` — tools: %s" % (name, tools or "(none declared)"))
        else:
            out.append("## Agent roles shipped — and the cage that did not come with them")
            out.append("")
            out.append("Each agent's prose, description and effort bound travel. The "
                       "per-agent TOOL allowlist does not: this runtime's role schema "
                       "has no field for it, so a role here may use any tool. What "
                       "follows is what each agent is restricted to on its home "
                       "runtime and is NOT restricted to here.")
            out.append("")
            for name, tools in roles:
                out.append("- `%s` — tools NOT enforced here: %s"
                           % (name, tools or "(none declared)"))
        out.append("")
    if projection.refusals:
        out.append("## Gates that are NOT protecting you here")
        out.append("")
        out.append(
            "Each of these is registered in the harness as a blocking gate and has "
            "no counterpart on this runtime. They are absent from the install rather "
            "than present and inert, because a gate that cannot fire is "
            "indistinguishable from one that protects.")
        out.append("")
        for r in projection.refusals:
            out.append("- %s" % r)
        out.append("")
    if lost:
        out.append("## Every registration that did not carry over")
        out.append("")
        for d in lost:
            out.append("- `%s` — %s" % (d.group, d.reason))
        out.append("")
    # Straight from the table: where each kind belongs, what the model line may say,
    # and every caveat measured on this runtime. Rendered from the declaration rather
    # than written per runtime, so a fact added to the table cannot go unprinted.
    carried_events = {d.event for d in projection.decisions if d.kind in _SURVIVES}
    for block in (render_placement(target or {}), render_model_rule(target or {}),
                  render_extra_events(target or {}, carried_events),
                  render_caveats(target or {})):
        if block:
            out.append(block.rstrip())
            out.append("")
    return "\n".join(out)
