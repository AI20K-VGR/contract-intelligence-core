"""docslib — thư viện chung cho 3 skill docs-*. SSOT = frontmatter + _index/*.yaml.

KHÔNG sáng tạo nội dung, KHÔNG phán chất lượng — chỉ parse / validate / generate view.
"""
import sys as _sys
from pathlib import Path as _Path

# frontmatter.py/index.py/manifest.py/graph.py/playbook.py import the shared
# yaml_io (harness/scripts/) at module top-level; this package's __init__ runs
# BEFORE any of them (the imports below), so this is the one place the
# bootstrap needs to happen for all five, rather than five copies of it.
# docslib/__init__.py → docslib → _docslib → skills → hs → plugins → harness.
_HARNESS_SCRIPTS = str(_Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in _sys.path:
    _sys.path.insert(0, _HARNESS_SCRIPTS)

from .findings import Finding, Findings, ERROR, WARN, INFO
from .frontmatter import Doc, parse, validate as validate_frontmatter, DOC_TYPES
from .discover import discover, iter_md
from .index import Model, Module, load_model
from .manifest import (
    Manifest, Page, Category, load_manifest, load_manifest_from_yaml, validate_manifest,
)
from .playbook import Playbook, load_playbook, PlaybookError
from .derived import DERIVED_OUTPUT_GLOBS, is_derived_output
from . import capabilities, graph, manifest, playbook, derived

__all__ = [
    "Finding", "Findings", "ERROR", "WARN", "INFO",
    "Doc", "parse", "validate_frontmatter", "DOC_TYPES",
    "discover", "iter_md", "Model", "Module", "load_model",
    "Manifest", "Page", "Category", "load_manifest", "load_manifest_from_yaml", "validate_manifest",
    "Playbook", "load_playbook", "PlaybookError",
    "DERIVED_OUTPUT_GLOBS", "is_derived_output",
    "capabilities", "graph", "manifest", "playbook", "derived",
]


def lib_root():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent
