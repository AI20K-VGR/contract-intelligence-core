#!/usr/bin/env python3
"""_spec_bridge — the ONE isolated-loader dance hs:shape uses to reach into
hs:spec's scripts (`spec_graph`, `frontmatter_parser`, `id_grammar`).

A naive `from spec_graph import build_graph` at module scope would collide
with the harness-internal docs-governance module of the same name already on
`sys.path` in-process (see `harness/tests/_spec_skill_import.py`), making
resolution order-dependent. Loading a name fresh under a save/restore of
`sys.modules`/`sys.path` avoids that hazard without hard-coupling hs:shape to
hs:spec's script layout beyond the one relative path below.

Every hs:shape reader that touches hs:spec's frontmatter/serves grammar goes
through this one loader instead of re-rolling the save/restore dance per
caller (`serves_resolver.py` and `experiment_spec.py` used to each carry a
near-identical private copy of this — collapsed here).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Sequence

# Dependency order matters: a module's own sibling imports must already be in
# sys.modules by the time it is exec'd (frontmatter_parser needs
# encoding_utils; spec_graph needs id_grammar + frontmatter_parser).
_ALL_NAMES = ("encoding_utils", "id_grammar", "frontmatter_parser", "spec_graph")


def spec_scripts_dir() -> Path:
    # .../shape/scripts/_spec_bridge.py -> .../spec/scripts
    return Path(__file__).resolve().parent.parent.parent / "spec" / "scripts"


def load_spec_modules(names: Sequence[str] = _ALL_NAMES):
    """Load `names` (in dependency order) from hs:spec's scripts dir under an
    isolated sys.modules/sys.path scope, then restore. Returns the LAST named
    module -- callers pass just the names they need (e.g. `("id_grammar",)`
    or `("encoding_utils", "frontmatter_parser")`) plus whatever those depend
    on."""
    scripts_dir = spec_scripts_dir()
    saved_mods = {n: sys.modules.get(n) for n in names}
    saved_path = list(sys.path)
    sys.path.insert(0, str(scripts_dir))
    for n in names:
        sys.modules.pop(n, None)
    try:
        for n in names:
            src = scripts_dir / (n + ".py")
            spec = importlib.util.spec_from_file_location(n, src)
            if spec is None or spec.loader is None:
                raise ImportError("cannot load hs:spec module %s from %s" % (n, src))
            module = importlib.util.module_from_spec(spec)
            sys.modules[n] = module
            spec.loader.exec_module(module)
        return sys.modules[names[-1]]
    finally:
        for n in names:
            if saved_mods[n] is not None:
                sys.modules[n] = saved_mods[n]
            else:
                sys.modules.pop(n, None)
        sys.path[:] = saved_path


# The three fixed module-set wrappers every hs:shape reader needs. Homed here
# (not re-defined per reader) so the dependency tuple for each is stated ONCE —
# a reader adding one is a one-line import, not another byte-identical copy of
# the isolated-load dance. Peer readers stay uncoupled from each other: they
# depend only on this bridge, which they already import.
def load_frontmatter_parser():
    """hs:spec's frontmatter_parser (+ its encoding_utils dep), isolated-loaded."""
    return load_spec_modules(("encoding_utils", "frontmatter_parser"))


def load_spec_graph():
    """hs:spec's spec_graph (+ id_grammar/frontmatter_parser/encoding_utils deps)."""
    return load_spec_modules(("encoding_utils", "id_grammar", "frontmatter_parser", "spec_graph"))


def load_id_grammar():
    """hs:spec's id_grammar (the parent-scoped ID grammar SSOT), isolated-loaded."""
    return load_spec_modules(("id_grammar",))
