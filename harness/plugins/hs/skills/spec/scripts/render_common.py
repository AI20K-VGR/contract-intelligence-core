#!/usr/bin/env python3
"""render_common — tiny shared helpers for the product-spec renderers.

product-spec-internal (inside the bundled skill tree — no manifest/packaging surface).
Home for the helpers that were byte-identically duplicated in `render_ascii` and
`render_ascii_board` (`_hashable`, `_is_deferred`, `_inline`, `_mark`). A neutral third
module avoids the existing render_ascii ↔ render_ascii_board circular-import (render_ascii
imports the board module at top level, the board module imports render_ascii lazily).

It is also the single home of `_CONTROL_RE`, the unsafe-char strip set shared by
EVERY render path — ascii (`_inline`), mermaid (`_safe_label`), and html
(`render_html_escape._escape`/`_tip_scalar` import it here) — so the terminal-escape
and Unicode-bidi neutralization is defined once and can never drift between paths.
`strip_control` wraps the same regex for RECORD-level (pre-serialization) use: the
hs:shape sidecar writers (`_sidecar`, `loop_handoff`) reach it through `_spec_bridge`
to neutralize frontmatter VALUES before `yaml.safe_dump`, sharing this one source.
It imports only the stdlib, so any render module can depend on it without a cycle.
"""

from __future__ import annotations

import re
from typing import Any, Dict

# Unsafe chars stripped at every render chokepoint. Two distinct threat classes:
#   1. C0 control bytes (minus the whitespace `.split()` already normalizes) + DEL:
#      an ESC (0x1b) / BEL (0x07) smuggled into a PO `title` via a legal YAML
#      double-quoted escape (`title: "x\e[2J..."`) would ride verbatim into the
#      render and be executed by whoever's terminal displays it (screen-clear,
#      title spoof, OSC-52 clipboard write) -- a terminal-escape injection.
#   2. Unicode bidirectional-override controls -- LRE/RLE/PDF/LRO/RLO (U+202A-202E)
#      and the isolate set LRI/RLI/FSI/PDI (U+2066-2069). These are Cf format chars
#      ABOVE the \x7f the C0 range caps at, so they need their own ranges. A hostile
#      RLO in a title visually reverses/hides adjacent text in any bidi-aware
#      terminal or browser -- the "Trojan Source" class (CVE-2021-42574).
# Both are hand-edited-field injections; both land in the same ascii/mermaid/html
# sinks, so both are stripped once here at the shared chokepoint.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


def strip_control(obj: Any) -> Any:
    """Recursively strip `_CONTROL_RE` from every string in a JSON-ish structure.

    Applied to a frontmatter RECORD before `yaml.safe_dump` so the serializer
    decides plain-vs-quoted style on the already-neutralized string. Stripping
    the *dumped text* afterward instead deletes a bidi char out of an unquoted
    scalar and leaves a bare token — `title: <RLO>true` → `title: true` — which
    silently retypes the value (str → bool/None/int) on re-parse. Doing the strip
    on the value keeps `"<RLO>true"` → `"true"`, which PyYAML then quotes
    (`title: 'true'`) so it round-trips back as the string the author typed.
    Dict keys are stripped too (a bidi in a key would corrupt the same way).
    """
    if isinstance(obj, str):
        return _CONTROL_RE.sub("", obj)
    if isinstance(obj, dict):
        out: Dict[Any, Any] = {}
        for k, v in obj.items():
            sk = strip_control(k)
            # A record re-read from a hand-edited file may carry a key with an
            # embedded control/bidi char (writers preserve arbitrary keys via
            # dict(fm)/dict(m) on update). If stripping collapses it onto a key
            # already present, refuse to silently drop the field (last-wins) —
            # surface the malformed record loudly instead. Clean records (distinct
            # literal keys) never collide, so this never fires on the normal path.
            if sk in out:
                raise ValueError(
                    "control/bidi char in a record key collapses onto existing "
                    "key %r after stripping — refusing to silently drop a field" % (sk,)
                )
            out[sk] = strip_control(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [strip_control(v) for v in obj]
    return obj


def _hashable(v: Any) -> str:
    """Coerce frontmatter values that should be enum scalars to a string.

    A PO who writes `status: [draft]` (list) or some other unhashable shape would
    otherwise crash dict indexing. Render the unexpected shape verbatim so the
    validator can flag `unknown_enum` separately, but never blow up the viz renderer.
    """
    if v is None:
        return "?"
    if isinstance(v, (list, dict, set)):
        return f"?{v!r}"
    return str(v)


def _is_deferred(node: Dict[str, Any]) -> bool:
    """A node is 'deferred' if either MoSCoW says won't OR scope says out."""
    return node.get("moscow") == "wont" or node.get("scope") == "out"


def _inline(s: Any) -> str:
    """Collapse any whitespace run (incl. CR/LF/tabs) to a single space and strip
    the ends. A free-text title written as a multi-line YAML scalar would otherwise
    inject extra lines into a one-line-per-node text summary or tree row, corrupting
    the deterministic grammar (and any naive line-count parser of the CI output).
    Mermaid's `_safe_label` collapses the same way.

    Also strips C0/DEL control bytes (see `_CONTROL_RE`) so a terminal-escape
    sequence smuggled into a PO title cannot execute in a viewer's terminal."""
    return _CONTROL_RE.sub("", " ".join(str(s).split()))


def _mark(node: Dict[str, Any], text: str) -> str:
    """Suffix the rendered text with a `*` when the node is deferred."""
    return f"{text} *" if _is_deferred(node) else text
