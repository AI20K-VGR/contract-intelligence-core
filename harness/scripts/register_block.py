#!/usr/bin/env python3
"""register_block.py — SSOT builder for the resolved-register context block.

Both context hooks — voice_inject (SessionStart) and subagent_init (SubagentStart)
— call build_register so the two surfaces cannot drift. The block carries the
terminal-voice axes, the universal-harm floor, the scope-fence, the persona line,
the interview knobs, and the audience / code_style register knobs — the one-line
essence + a MANDATORY directive to READ the profile file before writing the first
deliverable (diet C: the full MANDATORY/FORBIDDEN body is no longer dumped every
turn — body_for stays public for any skill that needs to slice it on demand).

Pure library, never raises: body_for reads a profile file inside try/except and
degrades to "" on any failure — it never blocks a session or a subagent (the callers
are telemetry-class, fail-open).
"""

from pathlib import Path

# Resolve the profile-body dir off this file (scripts/ -> ../data/output-styles/),
# never CWD — the hook runs with an arbitrary working directory.
_STYLES_DIR = Path(__file__).resolve().parent.parent / "data" / "output-styles"

_RULE = "harness/rules/terminal-voice.md"


def _register(level: int) -> str:
    """One-line terminal register descriptor for a voice_level (work-aimed)."""
    if level <= 2:
        return "polite, measured; soften hard news"
    if level <= 4:
        return "direct but courteous"
    if level == 5:
        return "blunt and direct, NO profanity (the default)"
    if level == 6:
        return "sharper - name a bad idea as bad, no hedging"
    if level == 7:
        return "roast the work; vi address form ong/toi or ba/toi"
    if level == 8:
        return "harsher; vi pronouns may/tao permitted"
    return "maximum bluntness; work-aimed profanity permitted (vi: đm/vl-tier)"


def _depth(level: int) -> str:
    return {
        0: "answer only, no explanation",
        1: "answer + one-line why",
        2: "brief reasoning",
        3: "reasoning + key trade-offs",
        4: "thorough reasoning",
        5: "full reasoning, context, and alternatives (the default)",
    }.get(level, "full reasoning, context, and alternatives (the default)")


def body_for(kind: str, level) -> str:
    """Return the MANDATORY/FORBIDDEN directive slice of a profile body, or "".

    Default install resolves audience/code_style to None — the common path, not an
    edge — so short-circuit on None BEFORE building any path or touching the
    filesystem (no `level-None.md` ever gets constructed or logged).

    Reads harness/data/output-styles/{kind}-level-{level}.md and keeps only the
    `## MANDATORY...` / `## FORBIDDEN...` sections: the H1, preamble, `---` rules,
    and any embedded `## Scope Fence` section are dropped — the register block
    carries its own scope-fence once, so re-emitting the file's copy would triple
    it. Any read failure → "" (fail-open, never raises)."""
    if level is None:
        return ""
    try:
        path = _STYLES_DIR / ("%s-level-%s.md" % (kind, level))
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except Exception:  # noqa: BLE001 - missing/unreadable profile → essence-only
        return ""
    return _slice_directives(text)


def _slice_directives(text: str) -> str:
    """Keep only the `## MANDATORY*` / `## FORBIDDEN*` sections of a profile body.

    Sections are delimited by level-2 headings (`## `); `### ` subheadings inside a
    section are NOT split points (they do not start with `## `). Content before the
    first `## ` (H1 + preamble) and any other section (e.g. `## Scope Fence`) is
    dropped."""
    sections = []
    current = None  # (heading_text, [lines]) once inside a kept section
    keep = False
    for line in text.splitlines():
        if line.startswith("## "):
            # Flush a finished kept section, then decide on the new heading.
            if keep and current is not None:
                sections.append("\n".join(current).rstrip())
            head = line[3:].strip().upper()
            keep = head.startswith("MANDATORY") or head.startswith("FORBIDDEN")
            current = [line] if keep else None
        elif keep and current is not None:
            current.append(line)
    if keep and current is not None:
        sections.append("\n".join(current).rstrip())
    return "\n\n".join(s for s in sections if s)


def build_register(prefs: dict, surface: str = "session") -> str:
    """The additionalContext register block: a POINTER at the rule file + the
    resolved knob values + the two non-negotiables (floor + scope-fence) + the
    audience / code_style essence AND profile BODY directives.

    `prefs` is the flat dict from output_config.resolve_all() (terminal-voice axes
    + output-config register knobs merged). Read straight off the dict — one
    source, no re-load, never raise (the resolver is fail-open by construction).

    `surface` picks how much of that block the reader actually needs:

      "session"  (default) — the full block. The main session talks to a human,
                 so the conversational half has a reader.
      "subagent" — drops the conversational half (harshness ladder, persona,
                 interview rigor, harm floor). A subagent's output goes to the
                 orchestrator, not to the user, so those lines shape nothing and
                 are paid for on every spawn. What survives is the register that
                 governs what it WRITES — audience, code_style, thinking_language
                 — plus the scope-fence, which is what stops any of them reaching
                 an evidence token.
    """
    import voice_prefs  # same scripts dir; lazy to keep this module import-light

    conversational = surface != "subagent"
    # Two independent reductions, deliberately not one flag.
    #
    #   `conversational` — WHO is reading. A subagent reports to the orchestrator,
    #   so nothing that shapes conversation with a human has a reader there.
    #
    #   `voice_surface` — whether this DEPLOYMENT wants a voice at all. A project
    #   settled on a neutral register gets no behaviour from the ladder, the
    #   persona, the harm floor, or the authority pointer, and pays for them on
    #   every SessionStart. `off` stops emitting them; it removes nothing, so `on`
    #   rebuilds the identical block.
    #
    # The interview knobs sit outside both: they steer how hard the assistant
    # probes before it builds, which is working, not talking.
    voice = conversational and str(prefs.get("voice_surface", "on")) != "off"

    cl = prefs["terminal_voice_level"]
    vl = prefs["voice_level"]
    persona = prefs["persona"]
    no_md = prefs["no_markdown"]
    # A persona bundle ABSORBS the persona knob: when one is active the surface
    # FORM comes from the bundle. ONLY the form crosses into build_register (the
    # shared SessionStart + SubagentStart surface) — it is scope-fenced and safe,
    # exactly like the standalone persona knob today. NAME/SOUL/RELATIONSHIP stay
    # main-only (appended in voice_inject.core), so a subagent never sees them.
    # Never raises: an id that no longer resolves falls back to the persona knob,
    # and a falsy persona_bundle leaves `form == persona` (byte-identical null path).
    form = persona
    bundle_id = prefs.get("persona_bundle")
    if bundle_id:
        # Defensive: build_register is telemetry-class and MUST NOT raise. Any
        # registry failure (unresolvable id, an unexpected import/parse error)
        # falls back to the persona knob rather than propagating.
        try:
            import persona_bundle  # lazy; leaf module, no import cycle
            _b = persona_bundle.resolve(bundle_id)
            if _b is not None:
                form = _b.get("form") or persona
        except Exception:  # noqa: BLE001 — never raise from the shared register builder
            form = persona
    lines = []
    if voice:
        lines += [
            "[Terminal voice - active session settings]",
            "Authority: %s (the harshness ladder, the universal-harm floor, the "
            "scope-fence, the persona catalog). Apply these to TERMINAL "
            "conversational prose ONLY." % _RULE,
            "voice_level=%d/9 - register: %s." % (vl, _register(vl)),
            "terminal_voice_level=%d/5 - explanation depth: %s." % (cl, _depth(cl)),
        ]
        if form and form != "none":
            lines.append(
                "persona=%s - adopt this surface form (catalog in %s); persona sets "
                "the FORM, voice_level sets the harshness inside it." % (form, _RULE))
        else:
            lines.append("persona=none - natural harness voice.")
        if no_md:
            lines.append(
                "no_markdown=true - answer in plain prose, no markdown formatting.")
        lines.append(
            "Universal-harm floor (NON-removable, holds at every level incl. 9): venom "
            "aimed at the WORK is allowed; anything aimed at WHO the user is - slurs, "
            "threats, sexual content, self-harm, family- or identity-targeted attacks "
            "- is OUT at every level.")

    # Outside the voice block on purpose: these two decide how hard to probe before
    # building, not how the answer sounds. A deployment that silenced the voice knobs
    # still wants its interview depth honoured.
    if conversational:
        lines.append(
            "[Interview] hs:plan / hs:discover / hs:brainstorm: interview_rigor=%s "
            "(depth of challenge / gap-probing), action_prompting=%s (density of "
            "next-step suggestions). Interview/turn verbosity rides "
            "terminal_voice_level." % (prefs["interview_rigor"], prefs["action_prompting"]))

    if voice:
        lines.append(
            "Scope-fence: these knobs change NOTHING in code, generated docs/reports, "
            "commits, evidence (file:line / IDs / SHAs / quotes), or any gate decision; "
            "and they do NOT control an artifact's own designed voice - the "
            "journal-writer keeps its brutal candor and the hs:critique report keeps "
            "its neutral tone at every voice_level.")
    else:
        # Same fence, phrased to stand on its own: the conversational knobs it
        # normally follows are not in this block, but the register knobs below
        # still must not reach an evidence token or an artifact's designed voice.
        lines.append(
            "Scope-fence: the register knobs below change NOTHING in code, commits, "
            "evidence (file:line / IDs / SHAs / quotes), or any gate decision; and "
            "they do NOT control an artifact's own designed voice - the "
            "journal-writer keeps its brutal candor and the hs:critique report keeps "
            "its neutral tone regardless.")

    # Output-config register knobs (audience / code_style / humanize) merged into
    # `prefs` by resolve_all(). Read off the dict — no re-load, never raise.
    audience_v = prefs.get("audience")
    code_style_v = prefs.get("code_style")
    humanize_v = prefs.get("humanize")

    aud_prof = voice_prefs.audience_profile(audience_v)
    if aud_prof:
        lines.append(
            "[Reader register - audience: shapes CHAT + report prose, NOT code/evidence]")
        # Summary then path, on ONE line. The summary has to stand on its own —
        # a pointer that forces the read is the cost it was meant to remove — and
        # the path is a POINTER, not a decree: reading both profiles in full cost
        # 5733 characters against a 2850-character block, paid once per session
        # whether or not anything in it applied. body_for stays public for
        # on-demand slicing of the MANDATORY/FORBIDDEN body.
        lines.append(
            "audience=%d/5 (%s): %s. Evidence tokens (file:line / IDs / SHAs / "
            "numbers / quotes) stay invariant at every level. Details when needed: %s."
            % (aud_prof["level"], aud_prof["name"], aud_prof["essence"],
               "harness/data/output-styles/audience-level-%d.md" % aud_prof["level"]))

    prof = voice_prefs.code_style_profile(code_style_v)
    if prof:
        lines.append("[Code style - adapts the DELIVERABLE, NOT scope-fenced]")
        # Summary + pointer on one line, same reasoning as the audience branch.
        lines.append(
            "code_style=%d/5 (%s): shape generated CODE only (comment density, "
            "verbosity, examples) - %s. Does NOT alter chat/report prose (that is "
            "`audience`). This axis is the deliberate EXCEPTION to the scope-fence "
            "above - it DOES change generated code/output. Details when needed: %s."
            % (prof["level"], prof["name"], prof["essence"],
               "harness/data/output-styles/code-style-level-%d.md" % prof["level"]))

    if humanize_v:
        lines.append(
            "humanize=on: apply harness/data/output-styles/humanizer-and-anti-ai-tells.md to "
            "externally-shipped reports; evidence invariant.")

    # Reasoning-language directive: the language the model THINKS in, separate from the
    # written-output language. A soft prompt nudge (no API param exists for it). Emit ONLY
    # when thinking_language differs from the output language — no point saying "think in en,
    # write in en". Scope-fenced like the other register knobs: shapes reasoning, never an
    # evidence token or a gate decision.
    tlang = prefs.get("thinking_language")
    olang = prefs.get("language")
    # State the OUTPUT language on its own line. It used to be mentioned only inside
    # the thinking-language directive below, which fires solely when the two differ —
    # so on the common config (both `vi`) the block named no language at all. The main
    # session recovers that from CLAUDE.md; a subagent has no such source and defaults
    # to English. Evidence tokens are exempt, same as everywhere else.
    if olang:
        lines.append(
            "[Output language]",
        )
        lines.append(
            "language=%s: write chat prose, reports, and generated docs in %s. "
            "Evidence tokens (file:line / IDs / SHAs / numbers / quotes) and "
            "instruction files (skills/rules/agents) are never translated."
            % (olang, olang))
    if tlang and tlang != olang:
        lines.append(
            "[Reasoning language - internal thinking only, NOT the written output]")
        lines.append(
            "thinking_language=%s: reason internally in %s for logic/precision; the written "
            "output stays in %s. Shapes the model's reasoning, never any evidence token "
            "(file:line / IDs / SHAs / numbers / quotes) or gate decision."
            % (tlang, tlang, olang))
    return "\n".join(lines)
