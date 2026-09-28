#!/usr/bin/env python3
"""Visualize the harness skill dependency graph as draw.io XML.

Reads harness/data/skill-deps.yaml (the skill dependency graph) and
harness/data/components.yaml (the group/category mapping) and emits
a JSON graph in the autolayout.py input contract.

Usage:
  python3 skillgraph.py [--skills cook,plan] [-o out.json]
                        [--deps-file PATH] [--components-file PATH]

Skill-selection contract:
  --skills a,b,c  → output = {a,b,c} + transitive deps (BFS closure on deps:).
  No --skills     → every skill in skill-deps.yaml.

Output JSON contract (autolayout.py input):
  {
    "direction": "TB",
    "nodes": [{"id": "<slug>", "label": "<slug>", "group": "<group>"}],
    "edges": [{"source": "<slug>", "target": "<dep-slug>"}]
  }

Node id = skill slug; edge direction = skill → dep (skill depends on dep).
Groups come from components.yaml. Spine skills not listed there get group "hs".
"""
import argparse
import json
import sys
from pathlib import Path

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing.
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)

try:
    import yaml_io
except ImportError:
    # Name still bound (None), no sys.exit here — a module-scope exit makes the
    # module impossible to import for inspection (pytest collection aborts with
    # INTERNALERROR). The "yaml_io required" exit happens in main() instead,
    # only when the CLI is actually invoked.
    yaml_io = None

_DEFAULT_DEPS = Path(__file__).resolve().parents[4] / "data" / "skill-deps.yaml"
_DEFAULT_COMPS = Path(__file__).resolve().parents[4] / "data" / "components.yaml"


def _load_yaml(path: Path) -> dict:
    try:
        return yaml_io.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml_io.YAMLError as e:
        print(f"Error parsing YAML {path}: {e}", file=sys.stderr)
        sys.exit(1)


def _build_group_map(comps_data: dict) -> dict:
    """Build skill -> group map from components.yaml."""
    group_map = {}
    comps = comps_data.get("components", {})
    for group_name, group_data in comps.items():
        for skill in group_data.get("skills", []):
            group_map[skill] = group_name
    return group_map


def _bfs_closure(seeds: set, deps_map: dict) -> set:
    """BFS transitive closure over the deps graph starting from seeds."""
    visited = set()
    queue = list(seeds)
    while queue:
        skill = queue.pop(0)
        if skill in visited:
            continue
        visited.add(skill)
        for dep in deps_map.get(skill, {}).get("deps", []):
            if dep not in visited:
                queue.append(dep)
    return visited


def build_graph(skills_data: dict, group_map: dict, seeds: "set | None") -> dict:
    """Build the autolayout-compatible graph JSON.

    skills_data: the 'skills' sub-dict from skill-deps.yaml.
    group_map: skill -> group from components.yaml.
    seeds: set of skill names to include (+ transitive). None = all.
    """
    if seeds is None:
        included = set(skills_data.keys())
    else:
        included = _bfs_closure(seeds, skills_data)

    nodes = []
    for skill in sorted(included):
        group = group_map.get(skill, "hs")
        nodes.append({"id": skill, "label": skill, "group": group})

    edges = []
    for skill in sorted(included):
        for dep in skills_data.get(skill, {}).get("deps", []):
            if dep in included:
                edges.append({"source": skill, "target": dep})

    return {"direction": "TB", "nodes": nodes, "edges": edges}


def main(argv=None) -> int:
    if yaml_io is None:
        print("Error: ruamel.yaml is required. Install with: "
              "pip install -r harness/requirements.txt", file=sys.stderr)
        return 1

    ap = argparse.ArgumentParser(
        description="Emit harness skill-dep graph as autolayout.py JSON."
    )
    ap.add_argument(
        "--skills",
        help="Comma-separated skill names to include (+ transitive deps). "
             "Omit to include all skills.",
    )
    ap.add_argument(
        "-o", "--output",
        help="Output JSON file path. Default: stdout.",
    )
    ap.add_argument(
        "--deps-file",
        help="Path to skill-deps.yaml (default: auto-detect from script location).",
    )
    ap.add_argument(
        "--components-file",
        help="Path to components.yaml (default: auto-detect from script location).",
    )
    args = ap.parse_args(argv)

    deps_path = Path(args.deps_file) if args.deps_file else _DEFAULT_DEPS
    comps_path = Path(args.components_file) if args.components_file else _DEFAULT_COMPS

    deps_data = _load_yaml(deps_path)
    comps_data = _load_yaml(comps_path)

    skills_map = deps_data.get("skills", {})
    if not skills_map:
        print("Error: no skills found in skill-deps.yaml", file=sys.stderr)
        return 1

    group_map = _build_group_map(comps_data)

    # Resolve seed set
    seeds = None
    if args.skills:
        raw = [s.strip() for s in args.skills.split(",") if s.strip()]
        unknown = [s for s in raw if s not in skills_map]
        if unknown:
            print(
                "Error: unknown skill(s) not found in skill-deps.yaml: "
                + ", ".join(repr(s) for s in unknown),
                file=sys.stderr,
            )
            return 1
        seeds = set(raw)

    graph = build_graph(skills_map, group_map, seeds)

    out_json = json.dumps(graph, indent=2, ensure_ascii=False)

    if args.output:
        try:
            Path(args.output).write_text(out_json, encoding="utf-8")
        except OSError as e:
            print(f"Error writing {args.output}: {e}", file=sys.stderr)
            return 1
    else:
        print(out_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
