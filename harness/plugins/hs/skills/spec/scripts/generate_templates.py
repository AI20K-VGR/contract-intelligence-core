#!/usr/bin/env python3
"""
generate_templates — instantiate one of the assets/templates/*.md templates
for a given artifact type, substitute {{tokens}}, drop optional sections the
caller did not request, allocate the next parent-scoped ID, and write the
output to the correct path under docs/product/.

Token substitution: simple {{name}} -> value replacement. Tokens not provided
become the literal string "TBD" (so the file is still valid; the PO fills in).

Optional sections: `<!-- OPTIONAL: name --> ... <!-- /OPTIONAL -->` blocks
are kept ONLY if `name` appears in --keep-optional (comma-separated). All
other optional blocks are dropped.

ID allocation: parent-scoped. The CLI allocates ONE id per invocation (it passes
an empty `session_used`). `allocate_id(..., session_used=[...])` is the library
entry point for callers that mint MULTIPLE ids in one process: pass the ids
already handed out this session so siblings under the same parent don't collide
(exercised by the tests).

CLI:
    generate_templates.py --root <project-dir> --type <type> [--slug <slug>] \\
        [--parent <id>] [--values <json-file-or-string>] \\
        [--keep-optional <name,name>] [--lang en|vi] [--write]

Examples:
    # Allocate a new story under PRD-AUTH-E1 from values.json
    generate_templates.py --root . --type story --parent PRD-AUTH-E1 \\
        --values values.json --keep-optional notes --write
"""

import argparse
import datetime as dt
import fcntl
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from encoding_utils import configure_utf8_console, write_text_atomic, emit_json
from fs_guard import FenceError, assert_under_docs_product
from spec_graph import build_graph
from template_id_alloc import (
    allocate_id,
    reject_prd_collision,
    ID_PATTERN_OVERRIDE,
)

configure_utf8_console()


TYPE_TEMPLATE = {
    "product": "product.md",
    "vision": "vision.md",
    "brd": "brd.md",
    "prd": "prd.md",
    "epic": "epic.md",
    "story": "story.md",
    "exec_summary": "exec-summary.md",
    "release_notes": "release-notes.md",
    "sign_off": "sign-off.md",
}

OUTPUT_PATH_FOR_TYPE = {
    "product": "PRODUCT.md",
    "vision": "vision.md",
    "brd": "brd.md",
    "prd": "prds/{slug}.md",
    "epic": "epics/{id}.md",
    "story": "stories/{id}.md",
    "exec_summary": "exec-summary.md",
    "release_notes": "release-notes.md",
}

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"

OPTIONAL_RE = re.compile(
    r"<!--\s*OPTIONAL:\s*(?P<name>[a-z0-9_-]+)\s*-->(?P<body>.*?)<!--\s*/OPTIONAL\s*-->",
    re.DOTALL,
)

TOKEN_RE = re.compile(r"\{\{(?P<key>[a-zA-Z0-9_]+)\}\}")

# Every character PyYAML's plain-scalar scanner treats as a line break. A token
# value carrying any of these can forge a second frontmatter line on re-read
# (see tok()'s guard). \n/\r are the obvious ones; \x85 (NEL), \u2028 (LINE
# SEPARATOR) and \u2029 (PARAGRAPH SEPARATOR) are the invisible-in-a-diff ones.
_YAML_LINE_BREAKS = "\n\r\x85\u2028\u2029"

# Any brace pair, valid key or not -- used by render()'s PRE-substitution
# residual scan (see the guard inside render()) to catch a malformed
# template token ({{bad-key}}, {{ spaced }}) that TOKEN_RE will never match
# and therefore never substitute.
RESIDUAL_TOKEN_RE = re.compile(r"\{\{.*?\}\}")



def render(template_text: str, values: Dict[str, Any], keep_optional: List[str]) -> str:
    keep_set = set(keep_optional or [])

    def opt_replace(m: re.Match) -> str:
        name = m.group("name")
        body = m.group("body")
        return body if name in keep_set else ""

    rendered = OPTIONAL_RE.sub(opt_replace, template_text)
    # A non-greedy match cannot consume a nested OPTIONAL block in one pass.
    # Any leftover <!-- OPTIONAL: ... --> or <!-- /OPTIONAL --> sentinels are
    # structural noise; strip them so they don't leak into the artifact.
    rendered = re.sub(r"<!--\s*/?OPTIONAL(?:\s*:.*?)?\s*-->", "", rendered)

    # Strip the leading template comment (everything between first '<!--' and '-->\n')
    # BEFORE the residual-token check, so an illustrative {{example-token}} inside
    # the soon-to-be-discarded header comment can't spuriously trip the guard.
    rendered = re.sub(r"\A\s*<!--.*?-->\s*\n", "", rendered, count=1, flags=re.DOTALL)

    # TOKEN_RE only matches [a-zA-Z0-9_]+ tokens, so keys containing hyphens,
    # spaces, or dots (e.g. {{bad-key}}, {{ spaced }}) are left literally in
    # the output. Detect and reject them so a malformed template fails loudly
    # instead of writing literal {{...}} into the artifact.
    #
    # This scan runs on the PRE-substitution text -- BEFORE tok() below ever
    # runs -- deliberately: a post-substitution scan (the old order) re-scans
    # the FULL rendered text including any caller-supplied VALUE that
    # json.dumps preserves verbatim (e.g. a list entry containing the literal
    # text "{{token}}"), misreading a legitimate value as an unresolved
    # template token. Scanning first means only the template's own {{...}}
    # spans are ever inspected; a valid key ([a-zA-Z0-9_]+) is left alone
    # here and substituted normally below.
    for residual in RESIDUAL_TOKEN_RE.finditer(rendered):
        if TOKEN_RE.fullmatch(residual.group()) is None:
            raise ValueError(
                f"unresolved template token {residual.group()!r} found after substitution; "
                f"token keys must match [a-zA-Z0-9_]+ — hyphens, spaces, and dots are not allowed"
            )

    def tok(m: re.Match) -> str:
        k = m.group("key")
        v = values.get(k)
        if v is None:
            return "TBD"
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        s = str(v)
        # Reject any character PyYAML's plain-scalar scanner folds into a line
        # break, not just \n/\r: a caller-supplied `--values
        # '{"owner":"x\u2028status: approved"}'` (U+2028 LINE SEPARATOR, or
        # U+2029 / U+0085 NEL — all invisible in a diff) re-materializes on
        # re-read as a SECOND YAML line, injecting a duplicate key like
        # `status: approved` and bypassing the approval guard in fill_defaults
        # (which only inspects the raw pre-substitution value). Multi-line
        # content belongs in body sections, not single-line frontmatter tokens.
        if any(ch in s for ch in _YAML_LINE_BREAKS):
            raise ValueError(
                f"value for token {{{{{k}}}}} contains a newline or Unicode "
                f"line separator; frontmatter tokens must be single-line scalars"
            )
        return s

    rendered = TOKEN_RE.sub(tok, rendered)

    return rendered


def _prd_slug_from_id(artifact_id: str) -> str:
    """Derive the lowercase slug from a PRD-<SLUG> id. The single home for this
    derivation; both output_path() and _run() call here so they never diverge."""
    return artifact_id[4:].lower()


def output_path(root: Path, target_type: str, artifact_id: str, slug: Optional[str]) -> Optional[Path]:
    """Return the output path for a type that has an OUTPUT_PATH_FOR_TYPE mapping,
    or None for content-only types (sign_off) that have no file home
    in the standard layout."""
    template = OUTPUT_PATH_FOR_TYPE.get(target_type)
    if template is None:
        return None
    # PRD: ensure slug is never empty (would produce `prds/.md`).
    # _prd_slug_from_id is the single derivation home — no inline re-derivation.
    if target_type == "prd" and not slug and artifact_id.upper().startswith("PRD-"):
        slug = _prd_slug_from_id(artifact_id)
    out_rel = template.format(id=artifact_id, slug=(slug or "").lower())
    return root / "docs" / "product" / out_rel


def load_values(spec: Optional[str]) -> Dict[str, Any]:
    if not spec:
        return {}
    p = Path(spec)
    try:
        if p.is_file():
            raw = json.loads(p.read_text(encoding="utf-8"))
        else:
            raw = json.loads(spec)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--values: invalid JSON ({exc})") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"--values: could not read file {spec!r} ({exc})") from exc
    if not isinstance(raw, dict):
        raise ValueError(
            f"--values: top-level JSON must be an object (mapping); "
            f"got {type(raw).__name__} — pass a JSON object like {{\"key\": \"value\"}}."
        )
    return raw


# List-typed frontmatter fields. If the caller omits them, default to [] so
# token substitution emits a valid YAML list — never the bare string "TBD"
# (which downstream renderers iterate per-character: persona viz would render
# rows 'T', 'B', 'D' and traceability would flag phantom dangling_link errors
# for refs T/B/D). Closed list per references/frontmatter-and-id-spec.md.
LIST_FIELDS = (
    "personas",
    "metrics",
    "brd_goals",
    "risks",
    "acceptance_criteria",
    # COMPETITION: the BRD's competitor-identity list. Same per-character-iteration
    # hazard as the other list fields, so default to [] (never the bare "TBD").
    "competitors",
)

# COMPETITION: a PRD's `competitive_parity` is an ID-keyed MAP, not a list, so it
# defaults to an empty mapping {} (token substitution emits valid YAML `{}`).
# Kept separate from LIST_FIELDS so the [] default doesn't mis-shape the map.
MAP_FIELDS = (
    "competitive_parity",
)


def fill_defaults(values: Dict[str, Any], target_type: str, artifact_id: str, lang: str) -> Dict[str, Any]:
    today = dt.date.today().isoformat()
    out = {
        "id": artifact_id,
        "status": "draft",
        "lang": lang,
        "owner": "TBD",
        "version": "0.1.0",
        "created": today,
        "updated": today,
    }
    for k in LIST_FIELDS:
        out[k] = []
    for k in MAP_FIELDS:
        out[k] = {}
    out.update(values)
    # A caller-supplied value for a structural field may be `None` (e.g.
    # {"personas": null}) OR any other non-list/non-dict scalar (e.g.
    # {"personas": "power users"} from a hand-typed `--values` string) --
    # both would otherwise ride through untouched and render as a bare YAML
    # scalar, which a downstream `for p in personas` reader char-splits into
    # single-letter "personas" (the same per-character-iteration hazard the
    # [] / {} default above already exists to prevent). `None` degrades to
    # the empty default (nothing to recover); any other scalar is wrapped
    # into a single-item list / discarded to {} instead of silently mis-
    # shaping the field.
    for k in LIST_FIELDS:
        v = out.get(k)
        if v is None:
            out[k] = []
        elif not isinstance(v, list):
            out[k] = [v]
    for k in MAP_FIELDS:
        v = out.get(k)
        if not isinstance(v, dict):
            out[k] = {}
    out["id"] = artifact_id
    # Defense-in-depth: generate never mints `approved` artifacts. Approval is
    # a separate explicit promotion flow (records owner + date + version bump).
    # Caller-supplied `status: approved` is the most common silent-approval
    # vector; reject it here so the script layer cannot be tricked into it
    # even if a higher layer's safeguards regress.
    if out.get("status") == "approved":
        raise ValueError(
            f"generate_templates refuses to create {target_type}={artifact_id!r} "
            f"with status='approved'. New artifacts must start as 'draft'. "
            f"Promote by editing the frontmatter directly (no scripted --approve "
            f"flow ships in this build)."
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--type", required=True, choices=sorted(TYPE_TEMPLATE.keys()))
    ap.add_argument("--slug", help="uppercase slug for PRD (e.g., AUTH)")
    ap.add_argument("--parent", help="parent ID for epic/story")
    ap.add_argument("--values", help="JSON file path OR JSON string of token values")
    ap.add_argument("--keep-optional", default="", help="comma-separated names of optional sections to keep")
    ap.add_argument("--lang", default="en", choices=["en", "vi"])
    ap.add_argument("--write", action="store_true", help="write the file (default: print only)")
    ap.add_argument(
        "--force", action="store_true",
        help="with --write: overwrite an existing file. Without --force, "
             "an existing path causes the script to refuse rather than "
             "silently clobber manual PO edits.",
    )
    ap.add_argument("--id", default=None, help="override allocated ID (used by --auto batch)")
    args = ap.parse_args()

    try:
        return _run(args)
    except (ValueError, FenceError) as exc:
        # Analytical script contract: a ValueError (bad input) or a FenceError (a
        # write blocked outside the spec boundary) surfaces as a JSON finding on
        # stdout — never a bare traceback (validation-rules-spec.md:30).
        response = {
            "type": args.type,
            "id": args.id or "",
            "path": None,
            "written": False,
            "content": None,
            "error": "invalid_input",
            "message": str(exc),
        }
        emit_json(response)
        return 0


def _run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    # A --write invocation runs {build graph -> allocate id -> exists-check ->
    # write} as one critical section. Without a lock, two concurrent PO-authoring
    # calls under the same parent read the same graph, allocate the same next id,
    # and the second write silently clobbers the first (both report written:true --
    # real data loss). Serialize the whole section on a sibling lock file, mirroring
    # dec_ledger.alloc's flock. A non-write (preview/print) invocation persists
    # nothing, so a stale-read id in its output is harmless and it needs no lock.
    if not args.write:
        return _run_locked(args, root)
    lock_path = root / "docs" / "product" / ".generate.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            return _run_locked(args, root)
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def _run_locked(args: argparse.Namespace, root: Path) -> int:
    graph = build_graph(root)
    keep_optional = [s.strip() for s in args.keep_optional.split(",") if s.strip()]
    values = load_values(args.values)

    if args.id:
        # A pre-allocated `--id` from an --auto braindump still has to honour
        # the parent-scoped grammar; otherwise the LLM batch could quietly
        # mint a story like `PRD-AUTH-S99` (missing the epic segment) and
        # the validator would only catch it on the next pass.
        pattern = ID_PATTERN_OVERRIDE.get(args.type)
        if pattern and not pattern.match(args.id):
            raise ValueError(
                f"--id {args.id!r} does not match expected pattern "
                f"{pattern.pattern} for type={args.type}"
            )
        # The grammar-pattern check above (ID_PATTERN_OVERRIDE["prd"]) alone
        # is not enough — a PRD id like PRD-AUTH-E9 legally matches BOTH the prd
        # and the epic pattern, so `--type prd --id PRD-AUTH-E9` and `--type epic
        # --id PRD-AUTH-E9` would both succeed and mint two artifacts sharing one
        # id. Run the same cross-type collision guard allocate_id() applies on
        # its --slug path (template_id_alloc.reject_prd_collision) — reused, not
        # duplicated, so the --id override path can never disagree with the
        # --slug mint path about what collides.
        if args.type == "prd":
            id_slug = args.id[4:] if args.id.upper().startswith("PRD-") else args.id
            reject_prd_collision(id_slug.upper(), f"--id {args.id!r}")
        # For type=prd, --id is authoritative: the file is placed at prds/<slug>
        # where slug = id[4:].lower(). If --slug is also given it MUST agree,
        # otherwise the file path (based on --slug) diverges from the frontmatter id
        # (based on --id) → mislocated artifact that validate won't catch.
        if args.type == "prd" and args.slug:
            id_slug = args.id[4:].lower() if args.id.upper().startswith("PRD-") else ""
            if id_slug != args.slug.lower():
                raise ValueError(
                    f"--id {args.id!r} and --slug {args.slug!r} are inconsistent: "
                    f"the slug implied by --id is {id_slug!r}. "
                    f"Either omit --slug (let --id drive the path) or align them."
                )
        artifact_id = args.id
    else:
        artifact_id = allocate_id(graph, args.type, args.slug, args.parent, session_used=[])

    # For types with no OUTPUT_PATH mapping (sign_off), the artifact is
    # content-only in the standard layout: --write on such a type is a no-op
    # (the caller gets the rendered content in the JSON response, nothing
    # written to disk).
    has_path_mapping = args.type in OUTPUT_PATH_FOR_TYPE

    # Derive slug from --id for type=prd when --slug is omitted, so the output path
    # never collapses to `prds/.md`. _prd_slug_from_id is the single home used by
    # both this derivation and output_path() — no duplication.
    effective_slug = args.slug
    if args.type == "prd" and not effective_slug and artifact_id.upper().startswith("PRD-"):
        effective_slug = _prd_slug_from_id(artifact_id)

    # For epic/story: when --id given without --parent, derive the parent ID from
    # the artifact_id so token substitution doesn't leave the parent token as 'TBD'
    # (a downstream dangling-link error).
    #
    # When BOTH --id and --parent are given, the parent implied by --id must
    # agree with --parent — otherwise `--type story --id PRD-FOO-E1-S1 --parent
    # PRD-FOO-E2` would write frontmatter `epic: PRD-FOO-E2` under an id whose
    # own shape says its epic is E1, corrupting the later graph edge. Same
    # derivation as the no-parent branch below, now also used as a consistency
    # check rather than only a default-fill.
    effective_parent = args.parent
    derived_parent = None
    if args.id:
        if args.type == "story" and "-S" in args.id:
            derived_parent = args.id.rsplit("-S", 1)[0]
        elif args.type == "epic" and "-E" in args.id:
            derived_parent = args.id.rsplit("-E", 1)[0]
    if args.parent and derived_parent and derived_parent != args.parent:
        raise ValueError(
            f"--id {args.id!r} and --parent {args.parent!r} are inconsistent: "
            f"the parent implied by --id is {derived_parent!r}. "
            f"Either omit --parent (let --id drive it) or align them."
        )
    if not effective_parent and derived_parent:
        effective_parent = derived_parent

    values = fill_defaults(values, args.type, artifact_id, args.lang)
    if effective_parent:
        if args.type == "story":
            values.setdefault("epic", effective_parent)
        elif args.type == "epic":
            values.setdefault("prd", effective_parent)

    template_path = TEMPLATES_DIR / TYPE_TEMPLATE[args.type]
    template_text = template_path.read_text(encoding="utf-8")
    rendered = render(template_text, values, keep_optional)

    out_path = output_path(root, args.type, artifact_id, effective_slug) if has_path_mapping else None
    response: Dict[str, Any] = {
        "type": args.type,
        "id": artifact_id,
        "path": (
            str(out_path.relative_to(root)) if (out_path is not None and out_path.is_relative_to(root))
            else (str(out_path) if out_path is not None else None)
        ),
        "written": False,
        "content": rendered,
    }
    if args.write and out_path is not None:
        if out_path.exists() and not args.force:
            response["error"] = "exists"
            response["message"] = (
                f"refusing to overwrite existing file: "
                f"{out_path.relative_to(root) if out_path.is_relative_to(root) else out_path}. "
                f"Pass --force to overwrite."
            )
            emit_json(response)
            return 0
        # Soft-fence: resolve + contain BEFORE mkdir/write so a crafted slug/parent
        # cannot place an artifact outside docs/product/.
        assert_under_docs_product(out_path, root)
        # Atomic write (temp + os.replace) so a concurrent reader of this fixed
        # docs/product path never catches it mid-truncate during a --force
        # re-render. write_text_atomic writes newline-verbatim (LF as authored,
        # byte-identical across platforms) and creates the parent dir itself.
        write_text_atomic(out_path, rendered)
        response["written"] = True

    emit_json(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
