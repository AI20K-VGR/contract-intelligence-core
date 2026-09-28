#!/usr/bin/env python3
"""yaml_io.py — the one shared YAML reader/writer for the whole harness tree.

── WHY THIS FILE EXISTS ──────────────────────────────────────────────────────
Ruling (docs decisions, 2026-07-29, re-affirmed 2026-08-02): replace PyYAML with
`ruamel.yaml` everywhere — "using two YAML readers in parallel in one repo creates
two different meanings for the same file." A partial swap (some call sites on
`ruamel`, others still on `yaml`) is exactly the thing the ruling forbids, so this
module is the SINGLE place that imports `ruamel.yaml`; every hook/script/plugin
reads and writes YAML through here, never through a second copy of this logic.

── WHY RUAMEL OVER PyYAML, IN ONE LINE ───────────────────────────────────────
YAML 1.1 (PyYAML) folds a bare `off`/`on`/`yes`/`no` into a bool; YAML 1.2 (ruamel)
keeps it a string. That is the "Norway problem" this repo hit for real
(`partner.yaml`'s `master: off`). `ruamel.yaml`'s `typ="safe"` loader also matches
`yaml.safe_load`'s output for every construct this repo's config actually uses
(scalars, mappings, sequences, dates — see test_yaml_io.py's parity sweep) while
adding: round-trip-safe comment preservation (for the writers that need it) and a
DuplicateKeyError raised by default instead of PyYAML's silent last-key-wins.

── WHY THE C ACCELERATOR IS NOT OPTIONAL HERE ────────────────────────────────
`ruamel.yaml` alone (pure Python) is measurably slower than PyYAML's C loader —
an early, incomplete measurement compared pure-Python ruamel against PyYAML's C
loader and reported "8.5x slower," which is what nearly reversed this ruling. With
`ruamel.yaml.clib` installed, `YAML(typ="safe", pure=False)` (the default — `pure`
only forces the Python path) uses the same libyaml-derived C parser/emitter, and
the real cost lands at ~2.49x the C-loader parse time, ~+5.8ms per fresh
interpreter's import — affordable against a real hook's 37-70ms. `clib` is
declared REQUIRED in harness/requirements.txt for exactly this reason: without it,
every hook process silently falls back to the slow path and the affordability math
this ruling is built on stops holding. `pure=False` is passed explicitly (rather
than relying on the ruamel default) so a reader of THIS file does not have to know
that default to know which path is taken.

── WHY THE NORWAY-SAFE REPRESENTER (the write side of the same trap) ─────────
Reading `off` as a string only closes half the loop. If this module dumped
`{"master": "off"}` with ruamel's plain-Python-string style, the result is the
BARE word `off` (ruamel's own resolver does not need to quote it — under YAML 1.2
it never was ambiguous). Any YAML-1.1 reader of that same file (PyYAML, a CI
action, a different tool entirely) then folds it back to `False` — this module
would have re-introduced, on the WRITE side, the exact bug the read side exists to
avoid. `_represent_str_norway_safe` forces single-quote style on any plain scalar a
YAML-1.1 resolver would tag as something other than a string.

That check asks the LIBRARY's 1.1 tables rather than a hand-written word list. The
list version only knew the 18 bool spellings, which left the rest of YAML 1.1's
implicit types open on the same write side — measured, `safe_dump({"k": "12:30"})`
emitted a bare `k: 12:30` that PyYAML read back as the integer 750. Octal, the
underscore-int shape and timestamps sat in the same gap. See `_folds_under_yaml_11`.

Output stays byte-identical to `yaml.safe_dump`'s for every real payload in this
repo, with a named exception in the strict direction: this module quotes some
scalar shapes PyYAML 6's dumper leaves bare. That divergence is not the three
examples it might look like from a quick read — it is five shape-FAMILIES, most
of them open-ended (any string matching the shape diverges, not a fixed list):
single-letter `y`/`n`/`Y`/`N` (the one CLOSED family, 4 strings); any
unsigned-exponent float PyYAML's dumper regex does not recognize, with or
without a decimal point (`1e5`, `1.0e5`, `5.e10` — PyYAML's float pattern
requires a signed exponent, so an unsigned one never matches at any digit
count); any signed leading-dot decimal (`+.5`, `-.5` — PyYAML's leading-dot
branch never allows a sign, ruamel's does); and ruamel's looser YAML-1.1 octal
match (`0800`, `0090` — a leading zero followed by a digit 8 or 9, which is not
a valid octal digit under either resolver's own spec, but ruamel's regex still
treats the shape as octal-like where PyYAML's rejects it outright). A sixth
shape, `0o17` (the YAML-1.2 octal spelling), also gets quoted, but for an
unrelated reason — ruamel's own 1.2 write-side self-consistency, not this
module's 1.1-resolver check, so it is not `_folds_under_yaml_11`'s doing.
Measured against every YAML file actually in the repo (walk each file, test
every string scalar it holds through `_folds_under_yaml_11`) at four scopes —
all files on disk, git-tracked only, tracked excluding `mutants/`, tracked
excluding `mutants/` and `plans/` — the file count and the count that carry a
scalar this module quotes both shift with scope (as of this check: 2020/39,
1934/28, 1934/28, 1892/28 respectively — re-derive with
`git ls-files | grep -E '\\.ya?ml$' | wc -l` for the denominator), but the
CONCLUSION holds at every scope checked: every file that carries a quoted
scalar carries a shape PyYAML quotes too — zero real files hit the divergence.

── API SHAPE (why two names for the same reader) ─────────────────────────────
`yaml_load(stream)` is the canonical name — it is what the hot-path guard
(test_yaml_fast_loader.py's TestTheHotPathNoLongerCallsSafeLoad) requires hooks and
the named hot scripts to call, so that a stray `.safe_load(...)` reappearing in a
hook is still caught as a regression. `safe_load` is the SAME function under the
name most of the ~250-site migration's call sites already use (`yaml.safe_load`),
kept so that migrating a call site is a rename of the module prefix, not a
rewrite of the call shape, across every file that is not on the hot-path guard's
list.

`safe_dump` mirrors `yaml.safe_dump`'s kwarg surface actually used in this repo
(`sort_keys`, `allow_unicode`, `default_flow_style`, `width`) — not the full
PyYAML kwarg set, which this repo never calls.

`YAMLError` is re-exported so `except yaml_io.YAMLError` (or a caller still
spelling it `except yaml.YAMLError` against the OLD import) catches the same
exception family ruamel raises (`ruamel.yaml.error.YAMLError`, the base of
`ParserError`/`ScannerError`/`DuplicateKeyError`, mirroring PyYAML's own
hierarchy shape).
"""

import io

from ruamel.yaml import YAML, YAMLError  # noqa: F401 -- re-exported for callers
from ruamel.yaml.nodes import ScalarNode
from ruamel.yaml.representer import SafeRepresenter
from ruamel.yaml.resolver import VersionedResolver

__all__ = ["yaml_load", "safe_load", "safe_dump", "YAMLError"]

_STR_TAG = "tag:yaml.org,2002:str"

# A real YAML-1.1 resolver, used purely as a LOOKUP TABLE on the write side: given
# a plain scalar, what tag would a 1.1 reader give it? Anything other than `str` is
# a scalar this module must quote. Resolution carries no parse state, so one
# module-level instance is reused (same rationale as _LOADER below).
_V11 = VersionedResolver(version=(1, 1))


def _folds_under_yaml_11(text: str) -> bool:
    """True when a YAML-1.1 reader would turn this PLAIN scalar into a non-string.

    Why a resolver instead of the word list this used to carry: the list held the 18
    bool spellings and nothing else, so it closed the Norway trap and left the rest
    of YAML 1.1's implicit types wide open on the write side. Measured, the biggest
    survivor was the base-60 shape — `safe_dump({"k": "12:30"})` emitted a bare
    `k: 12:30`, which PyYAML read back as the integer 750. Octal (`0755` → 493),
    underscore ints (`1_000` → 1000) and timestamps (`2026-08-02` → a date) sat in
    the same gap. Asking the library's own 1.1 tables covers the whole class at once
    and cannot drift out of sync with them the way a transcribed regex would.

    Deliberately MORE conservative than PyYAML's dumper in one direction: ruamel's
    1.1 resolver folds `y`/`n` where PyYAML 6 does not, so those are now quoted too.
    Quoting a scalar that did not strictly need it costs a diff; leaving one bare
    that did need it costs the value. The safe direction is the quoted one.
    """
    return str(VersionedResolver.resolve(_V11, ScalarNode, text, (True, False))) != _STR_TAG


_LOADER = None


def _loader() -> YAML:
    """The one process-wide safe-loader instance. Cached like hook_runtime's old
    `_YAML_LOADER` cached the loader CLASS -- here it is the loader OBJECT, since
    ruamel's fast path is selected on the instance (`pure=False`), not a module
    attribute. Reused across calls: `YAML.load` carries no state across parses."""
    global _LOADER
    if _LOADER is None:
        y = YAML(typ="safe", pure=False)
        y.allow_unicode = True
        _LOADER = y
    return _LOADER


def _represent_str_norway_safe(representer, data):
    style = "'" if _folds_under_yaml_11(data) else None
    return representer.represent_scalar(_STR_TAG, data, style=style)


# Registered once, at import time, on the SafeRepresenter class -- every
# `YAML(typ="safe")` instance (this module's and any future one) picks it up,
# matching PyYAML's own SafeDumper being a fixed global class.
SafeRepresenter.add_representer(str, _represent_str_norway_safe)


def yaml_load(stream):
    """Parse `stream` (str, bytes, Path, or an open file object) and return the
    Python value. The canonical name hot-path callers (hook_runtime.py and the
    named hot scripts) must use -- see the module docstring's API SHAPE note."""
    return _loader().load(stream)


# Same function, PyYAML-shaped name -- the migration rename for every call site
# that is not on the hot-path guard's list (see module docstring).
safe_load = yaml_load


def safe_dump(data, stream=None, *, sort_keys=True, allow_unicode=True,
              default_flow_style=False, width=None):
    """Drop-in for `yaml.safe_dump`, restricted to the kwargs this repo's call
    sites actually pass. Returns a str when `stream` is None (matching
    `yaml.safe_dump`'s no-stream form); writes to `stream` and returns None
    otherwise (matching `yaml.safe_dump(data, stream)`)."""
    y = YAML(typ="safe", pure=False)
    y.default_flow_style = default_flow_style
    y.allow_unicode = allow_unicode
    y.sort_base_mapping_type_on_output = sort_keys
    if width is not None:
        y.width = width
    if stream is not None:
        y.dump(data, stream)
        return None
    buf = io.StringIO()
    y.dump(data, buf)
    return buf.getvalue()
