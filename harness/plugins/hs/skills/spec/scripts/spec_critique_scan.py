#!/usr/bin/env python3
"""
spec_critique_scan — MAP layer feeding hs:critique's lens fan-out on a spec
artifact (vision/BRD/PRD/epic/story under docs/product/).

Two jobs, both deterministic and no-LLM:

1. `lens_set_for(artifact_path)` — the resolver the EXPLICIT `--lenses` route
   reads. hs:critique's classifier only knows plan/decision/design/code/diff
   (critique/SKILL.md step 1); a spec artifact is never auto-picked, so the
   caller (hs:spec / a user) resolves the lens set here and passes it as
   `--lenses <csv>`. Returns None for any non-spec-artifact path — the
   classifier-driven route for plan/code/etc. is untouched.

2. `build_scan(root, target_id)` — the citation-ground-truth bundle a spec lens
   agent reads: `source_files` keyed by artifact ID, line-numbered against the
   REAL file text (never a guessed line), plus `structural_findings` (the
   structural validate output, degrading to an empty list only on a genuine
   failure — never fabricated).

This module does NOT judge quality, consolidate lens findings, or apply voice —
that is hs:critique-consolidator's job (fed by the lenses, not by this scan).
Adding a second consolidator/humanizer here would double-implement hs:critique;
see harness/plugins/hs/skills/spec/references/spec-critique.md.

CLI:
    spec_critique_scan.py --root <dir> --target <artifact-id>   # bundle JSON
    spec_critique_scan.py --lens-set-for <path>                 # lens-set JSON
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing. APPEND
# (never insert at 0): this skill directory also has its OWN encoding_utils.py
# / spec_graph.py, distinct modules with the SAME names as the harness/scripts
# copies -- prepending harness/scripts would shadow the local ones (see
# harness/tests/_spec_skill_import.py's docstring for the exact hazard).
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

from encoding_utils import configure_utf8_console, emit_json, read_text_utf8
from spec_graph import ancestors, build_graph_with_artifacts, index_artifacts

configure_utf8_console()

# harness/plugins/hs/skills/spec/scripts/spec_critique_scan.py -> harness/ is 5
# parents up. Computed off __file__ (never CWD) so this resolves correctly
# under a global install too (critique.yaml is a bin-global config — see
# harness/scripts/critique_config.py's own comment on that).
_HARNESS_ROOT = Path(__file__).resolve().parents[5]
_CRITIQUE_YAML = _HARNESS_ROOT / "data" / "critique.yaml"

# The directory-name -> spec-family key map. "spec" is the generic fallback
# (PRODUCT.md, or anything else under docs/product/ that isn't one of the more
# specific buckets) — critique.yaml maps ALL of these to the same lens list
# today; kept as separate keys so a future divergence (e.g. a story-only lens)
# is a one-line critique.yaml edit, not a resolver rewrite.
_DIR_TO_TYPE = {"prds": "prd", "epics": "epic", "stories": "story"}
_STEM_TO_TYPE = {"vision": "vision", "brd": "brd"}


def _infer_spec_type(artifact_path) -> Optional[str]:
    """Classify a path into a critique.yaml spec-family key, or None when the
    path is not a spec artifact at all (plan/code/anything else) — the classifier-
    driven route in hs:critique owns those, this resolver must stay out of the way.

    Path-based, not content-based: works even for a path that does not exist yet
    (e.g. a story being drafted), and never opens the file just to route it."""
    p = Path(artifact_path)
    stem = p.stem.lower()
    if stem in _STEM_TO_TYPE:
        return _STEM_TO_TYPE[stem]
    parent = p.parent.name.lower()
    if parent in _DIR_TO_TYPE:
        return _DIR_TO_TYPE[parent]
    if p.name == "PRODUCT.md":
        return "spec"
    # Anything else living under a docs/product/ tree (a hand-authored artifact
    # in a non-standard subdir, or PRODUCT.md itself) falls into the generic
    # "spec" bucket rather than being silently dropped.
    parts = [x.lower() for x in p.parts]
    if "docs" in parts and "product" in parts:
        return "spec"
    return None


def _load_spec_lenses(critique_path=None) -> Dict[str, Any]:
    p = Path(critique_path) if critique_path else _CRITIQUE_YAML
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — deliberate fail-soft
        # A missing critique.yaml raises FileNotFoundError, but a malformed one
        # can raise well past yaml_io.YAMLError: an explicit-tag scalar (e.g.
        # `x: !!timestamp 'not a ts'`) makes PyYAML's constructor raise a bare
        # AttributeError, and an out-of-range date raises a bare ValueError.
        # None of those are worth crashing the lens resolver over — degrade to
        # "no spec lenses configured" the same as a missing file.
        return {}
    if not isinstance(raw, dict):
        return {}
    lenses = raw.get("lenses")
    return lenses if isinstance(lenses, dict) else {}


def lens_set_for(artifact_path, critique_path=None) -> Optional[List[str]]:
    """Resolve the spec lens-set (list of agent slugs) for `artifact_path`, or
    None when the path is not a spec-family artifact. `critique_path` overrides
    the tracked harness/data/critique.yaml (tests only)."""
    spec_type = _infer_spec_type(artifact_path)
    if spec_type is None:
        return None
    lenses = _load_spec_lenses(critique_path)
    found = lenses.get(spec_type)
    if found is not None:
        return list(found)
    return list(lenses["spec"]) if "spec" in lenses else None


def _line_numbered(text: str) -> List[str]:
    """`<n>: <text>` per line, 1-based — the exact citation-ground-truth format
    every spec lens agent is told to cite (`<artifact_id>:<line>`)."""
    return ["%d: %s" % (i, line) for i, line in enumerate(text.splitlines(), start=1)]


def _artifact_source_lines(root: Path, art: Dict[str, Any]) -> List[str]:
    """Line-number the artifact's REAL file text (frontmatter + body, as it sits
    on disk) — never the parsed body alone, since a citation may point at a
    frontmatter line (e.g. an `acceptance_criteria` entry)."""
    file_rel = art.get("file")
    if not file_rel:
        return []
    path = root / "docs" / "product" / file_rel
    try:
        text = read_text_utf8(path)
    except OSError:
        return []
    return _line_numbered(text)


def _structural_findings_best_effort(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Read the structural validate findings for the already-built `graph`,
    degrading to an empty list on any failure (advisory / no-LLM contract —
    never fabricate a finding, never hard-fail this scan). Import is LOCAL —
    a same-directory sibling import, not a hard module-load dependency."""
    try:
        import check_traceability
        return check_traceability.check(graph)
    except Exception:  # noqa: BLE001 — advisory scan: degrade, never crash the bundle
        return []


def build_scan(root, target_id: str) -> Dict[str, Any]:
    """Build the citation-ground-truth bundle a spec critique lens reads.

    Deterministic, no-LLM: parses docs/product/ once via spec_graph, then
    line-numbers the target artifact plus every declared ancestor (vision/BRD
    goal/PRD/epic) into `source_files` — the ONLY citation ground truth a lens
    may cite against. A target id with no matching artifact yields an empty
    `source_files` entry rather than a fabricated one.
    """
    root = Path(root)
    graph, artifacts = build_graph_with_artifacts(root)
    index = index_artifacts(artifacts)
    ids = {target_id} | ancestors(graph, target_id)

    source_files: Dict[str, List[str]] = {}
    for aid in sorted(ids):
        art = index.get(aid)
        if art is None and aid.startswith("BRD-G"):
            # A BRD goal has no standalone artifact (goals live inside brd.md) —
            # cite against the BRD's own file so a goal-anchored finding still
            # points at real, on-disk lines.
            art = index.get("BRD")
        if art is None or not art.get("ok"):
            continue
        lines = _artifact_source_lines(root, art)
        if lines:
            source_files[aid] = lines

    return {
        "bundle_version": 1,
        "target_ids": [target_id],
        "source_files": source_files,
        "structural_findings": _structural_findings_best_effort(graph),
        "root_path": str(root),
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="spec-artifact critique scan bundle + --lenses resolver for hs:critique")
    ap.add_argument("--root", default=".", help="project root (contains docs/product/)")
    ap.add_argument("--target", default=None, help="artifact id to scan (e.g. PRD-AUTH-E1-S1)")
    ap.add_argument("--lens-set-for", dest="lens_set_for", default=None,
                     help="print the resolved lens set (or null) for the given artifact path")
    args = ap.parse_args(argv)

    if args.lens_set_for is not None:
        emit_json({"artifact_path": args.lens_set_for,
                   "lens_set": lens_set_for(args.lens_set_for)})
        return 0

    if not args.target:
        sys.stderr.write("spec_critique_scan.py: --target <artifact-id> required "
                          "(or use --lens-set-for <path>)\n")
        return 2

    emit_json(build_scan(Path(args.root).resolve(), args.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
