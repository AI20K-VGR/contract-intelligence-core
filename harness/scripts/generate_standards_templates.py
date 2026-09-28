#!/usr/bin/env python3
"""generate_standards_templates — instantiate a standards template skeleton.

Reads a template under harness/standards/templates/, substitutes {{tokens}}
(unfilled → "TBD" so the file stays valid for the author to fill), allocates the
next parent-scoped id using the SAME ID_PATTERN_BY_TYPE the builder owns
(imported from standards_graph — never re-encoded), and writes the output through
the standards fs_guard zone so the generator disciplines its own writes.

Parent-scoped id allocation: scan the existing graph for ids under the requested
parent and mint the next free suffix (ARCH-G<n> / STD-<SLUG> / STD-<...>-RG<n> /
STD-<...>-RG<n>-R<n>). The grammar lives in standards_graph; this module reuses
it as the validation rule so a generate-time id fast-fails the same way a
validate-time id would.

CLI:
    generate_standards_templates.py --root <project-dir> --type <type> \\
        [--slug <slug>] [--parent <id>] [--values <json>] [--write]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import standards_graph
from encoding_utils import configure_utf8_console
from fs_guard import assert_under, FenceError
from standards_graph import ID_PATTERN_BY_TYPE

configure_utf8_console()


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "standards" / "templates"

# Templates per output format. `yaml` is the pure-YAML SSOT (default): the whole
# file is one YAML mapping, prose in description/rationale block scalars, no
# markdown body. `md` is the legacy frontmatter+body form, kept reachable via
# --format md for back-compat with trees authored before the SSOT migration.
TEMPLATE_BY_FORMAT = {
    "yaml": {
        "stack": "STACK.std.yaml.tmpl",
        "charter": "charter.std.yaml.tmpl",
        "std_area": "STD-AREA.std.yaml.tmpl",
    },
    "md": {
        "stack": "STACK.md.tmpl",
        "charter": "charter.md.tmpl",
        "std_area": "STD-AREA.md.tmpl",
    },
}

# Output path under harness/standards/ per type and format.
OUTPUT_PATH_BY_FORMAT = {
    "yaml": {
        "stack": "STACK.std.yaml",
        "charter": "charter.std.yaml",
        "std_area": "areas/{id}.std.yaml",
    },
    "md": {
        "stack": "STACK.md",
        "charter": "charter.md",
        "std_area": "areas/{id}.md",
    },
}

DEFAULT_FORMAT = "yaml"

# The set of supported types is format-independent (same keys in every format).
TYPE_TEMPLATE = TEMPLATE_BY_FORMAT["yaml"]

TOKEN_RE = re.compile(r"\{\{(?P<key>[a-zA-Z0-9_]+)\}\}")

# A bare std-area slug fast-fail (uppercase letter start, ≤15 trailing chars).
_SLUG_RE = re.compile(r"^[A-Z][A-Z0-9-]{0,15}$")


def load_template(target_type: str, fmt: str = DEFAULT_FORMAT) -> str:
    """Return the raw template skeleton text for a target type + output format."""
    by_type = TEMPLATE_BY_FORMAT.get(fmt)
    if by_type is None:
        raise ValueError(f"no templates for format {fmt!r}; "
                         f"known: {sorted(TEMPLATE_BY_FORMAT)}")
    name = by_type.get(target_type)
    if not name:
        raise ValueError(f"no template for type {target_type!r}; "
                         f"known: {sorted(by_type)}")
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def render(template_text: str, values: Dict[str, Any]) -> str:
    """Substitute {{tokens}}; an unfilled token becomes the literal 'TBD'."""
    def sub(m: re.Match) -> str:
        v = values.get(m.group("key"))
        if v is None:
            return "TBD"
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        s = str(v)
        if "\n" in s or "\r" in s:
            raise ValueError(
                f"value for token {{{{{m.group('key')}}}}} contains a newline; "
                f"frontmatter tokens must be single-line scalars")
        return s
    return TOKEN_RE.sub(sub, template_text)


def _next_with_prefix(existing: set, prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    used = [int(m.group(1)) for x in existing
            if (m := pattern.match(x or ""))]
    n = (max(used) + 1) if used else 1
    return f"{prefix}{n}"


def allocate_id(graph: Dict[str, Any], target_type: str,
                slug: Optional[str], parent: Optional[str],
                session_used: Optional[List[str]] = None) -> str:
    """Allocate the next parent-scoped id for `target_type`.

    `session_used` lists ids already handed out this session so siblings under
    the same parent do not collide (single-invocation callers pass None/[])."""
    existing = {n["id"] for n in graph["nodes"]} | set(session_used or [])

    if target_type == "arch_goal":
        return _next_with_prefix(existing, "ARCH-G")

    if target_type == "std_area":
        if not slug:
            raise ValueError("--slug is required for type=std_area")
        normalised = slug.upper()
        if not _SLUG_RE.match(normalised):
            raise ValueError(
                f"--slug must be uppercase ASCII (A-Z, 0-9, hyphen), start with a "
                f"letter, ≤16 chars (matches {_SLUG_RE.pattern}); got {slug!r}")
        new_id = f"STD-{normalised}"
        if not ID_PATTERN_BY_TYPE["std_area"].match(new_id):
            raise ValueError(f"generated id {new_id} fails the std_area grammar")
        return new_id

    if target_type == "rule_group":
        if not parent or not ID_PATTERN_BY_TYPE["std_area"].match(parent):
            raise ValueError(
                f"--parent must be a valid std_area id (STD-<SLUG>) for "
                f"type=rule_group; got {parent!r}")
        return _next_with_prefix(existing, f"{parent}-RG")

    if target_type == "rule":
        if not parent or not ID_PATTERN_BY_TYPE["rule_group"].match(parent):
            raise ValueError(
                f"--parent must be a valid rule_group id (STD-<SLUG>-RG<n>) for "
                f"type=rule; got {parent!r}")
        return _next_with_prefix(existing, f"{parent}-R")

    if target_type == "stack":
        return "STACK"
    if target_type == "charter":
        return "CHARTER"
    return ""


def write_artifact(path: Path, content: str, root: Path, *, force: bool = False) -> Path:
    """Write `content` to `path`, refusing any target outside the standards zone.

    assert_under resolves and contains the target BEFORE the write, so a blocked
    path never touches disk (it raises FenceError). Refuses to clobber an existing
    artifact unless `force`: std_area ids are slug-deterministic, so a re-run for
    the same slug would otherwise silently overwrite a hand-authored area and the
    rule_groups/rules nested under it."""
    safe = assert_under(path, "standards", root=root)
    if safe.exists() and not force:
        raise ValueError(
            "%s already exists — pass --force to overwrite (a re-run would "
            "discard hand-authored content)" % safe.relative_to(root))
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(content, encoding="utf-8")
    return safe


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--type", required=True, choices=sorted(TYPE_TEMPLATE))
    ap.add_argument("--slug", default=None)
    ap.add_argument("--parent", default=None)
    ap.add_argument("--values", default=None, help="JSON string or @file of token values")
    ap.add_argument("--write", action="store_true", help="write the artifact (else print)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing artifact (default: refuse)")
    ap.add_argument("--format", default=DEFAULT_FORMAT,
                    choices=sorted(TEMPLATE_BY_FORMAT),
                    help="output format: yaml = pure-YAML SSOT (default), "
                         "md = legacy frontmatter+body (back-compat)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    # EVERY operator-input error exits 2 with a one-line message — never a raw
    # traceback from a dev-facing generator, and never exit 1 (block = exit 2 per
    # the harness convention). Covers: bad --values JSON / unreadable @file, an
    # invalid --slug/--parent the allocator rejects, a user-supplied id that
    # fails the grammar, an unfillable template token, and a write outside the
    # standards zone (FenceError).
    try:
        values: Dict[str, Any] = {}
        if args.values:
            raw = args.values
            if raw.startswith("@"):
                try:
                    raw = Path(raw[1:]).read_text(encoding="utf-8")
                except OSError as e:
                    raise ValueError("bad --values @file: %s" % e)
            try:
                values = json.loads(raw)
            except ValueError as e:
                raise ValueError("bad --values JSON: %s" % e)
            if not isinstance(values, dict):
                raise ValueError("bad --values: must be a JSON object")

        graph = standards_graph.build_graph(root)
        # Only allocate when no id was supplied — `setdefault` would eagerly
        # evaluate allocate_id (and demand --slug) even for a user-supplied id.
        if args.type in ("std_area", "rule_group", "rule", "arch_goal") \
                and "id" not in values:
            values["id"] = allocate_id(graph, args.type, args.slug, args.parent)
        # A user-supplied id (via --values) skips allocate_id; validate it against
        # the SAME grammar the builder enforces, so the generator never scaffolds
        # an artifact that fails its own gate (the module's stated guarantee).
        vid = values.get("id")
        pat = ID_PATTERN_BY_TYPE.get(args.type)
        if vid is not None and pat is not None and not pat.match(str(vid)):
            raise ValueError(
                "id %r fails the %s grammar (%s)" % (vid, args.type, pat.pattern))

        rendered = render(load_template(args.type, args.format), values)
        out_rel = OUTPUT_PATH_BY_FORMAT[args.format][args.type].format(
            id=values.get("id", "TBD"))
        out_path = standards_graph.standards_dir(root) / out_rel

        if args.write:
            written = write_artifact(out_path, rendered, root, force=args.force)
            print(str(written.relative_to(root)))
        else:
            sys.stdout.write(rendered)
        return 0
    except (ValueError, OSError, FenceError) as e:
        sys.stderr.write("error: %s\n" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
