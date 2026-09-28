#!/usr/bin/env python3
"""Static denylist scan for sandboxed code-fill (R9 layer 1).

HONESTY: a static denylist is NOT sandbox-proof. It is bypassable -- string
getattr indirection (getattr(__import__("os"), "system")), an attribute-chain
trick, str.encode/compile round-trips, or an os.posix_spawn variant this list
did not anticipate. This scanner is LAYER 1 of a layered jail: layer 2 is OS
containment (bubblewrap when available) plus environment scrubbing, a
no-network preamble, and a wall-clock timeout on the run; the final gate is a
human reading the run evidence. Because a static scan can be evaded, the real
OS jail carries the load in that layered design -- this denylist is a cheap
pre-filter that stops accidents, not a barrier that stops a determined
adversary.

CLI: python3 sandbox_denylist.py <file...>
  exit 0 -- every file scanned clean
  exit 1 -- at least one finding, no parse error (each printed as file:line: code: message)
  exit 2 -- at least one file failed to parse (a refusal: code that will not
            parse will not run, so it never reaches the sandbox)
"""

from __future__ import annotations

import ast
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Finding:
    line: int
    code: str
    message: str


_NETWORK_MODULES = {
    "socket", "_socket", "ssl", "_ssl", "http", "urllib", "urllib3",
    "requests", "httpx", "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "aiohttp", "websocket", "asyncio",
}

_EXEC_IMPORT_MODULES = {"subprocess", "pty", "ctypes", "multiprocessing"}

# os.<attr>(...) calls that spawn/replace a process. Enumerated explicitly --
# a glob on os.spawn* misses posix_spawn/posix_spawnp, a glob on os.exec*
# misses forkpty. os.fork and os.posix_spawn are known real-world evasions of
# a socket-only or naive denylist and MUST stay in this set.
_OS_PROCESS_CALLS = {
    "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp",
    "execvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv",
    "spawnve", "spawnvp", "spawnvpe",
}

_BUILTIN_EXEC_CALLS = {"eval", "exec", "compile", "__import__"}

# os names that read the process environment -- reachable either as os.<name>
# or pulled in directly with `from os import <name>`.
_OS_ENV_NAMES = {"environ", "getenv"}

_PATH_WRITE_METHODS = {"write_text", "write_bytes"}

# Common tokens across the regex-lane languages, plus a per-lang extension --
# an internal dict so a wave-2 language just adds an entry.
_REGEX_COMMON_TOKENS = ("http://", "https://")
_REGEX_LANG_TOKENS = {
    "js": ("fetch(", "XMLHttpRequest", "child_process", "process.env", "exec("),
    "javascript": ("fetch(", "XMLHttpRequest", "child_process", "process.env", "exec("),
    "ts": ("fetch(", "XMLHttpRequest", "child_process", "process.env", "exec("),
    "go": ("net.Dial", "os.Getenv", "exec.Command"),
    "rust": ("env::var",),
}


def _root_module(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def _callee_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _string_literal(node: Optional[ast.expr]) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _scan_import(node) -> List[Finding]:
    findings: List[Finding] = []
    is_from = isinstance(node, ast.ImportFrom)
    names = [node.module] if is_from else [alias.name for alias in node.names]
    verb = "from {} import ...".format(node.module) if is_from else None
    for name in names:
        if not name:
            continue
        root = _root_module(name)
        label = verb or "import of '{}'".format(name)
        if root in _NETWORK_MODULES:
            findings.append(Finding(node.lineno, "network",
                "{} reaches the network stack; drop the dependency or use "
                "a stdlib-only stub".format(label)))
        elif root in _EXEC_IMPORT_MODULES:
            findings.append(Finding(node.lineno, "exec",
                "{} can spawn a process; code-fill must not shell out".format(label)))
        elif root == "importlib":
            findings.append(Finding(node.lineno, "dynamic-import",
                "{} enables dynamic import; use a static import instead".format(label)))

    # `from os import system` / `from os import environ` pull a dangerous name
    # into the module namespace as a bare identifier, sidestepping the
    # `os.<attr>` call/attribute checks entirely -- flag the danger at the
    # import itself. Innocent submodule/name imports (os.path, getcwd) are
    # untouched.
    if is_from and _root_module(node.module or "") == "os":
        for alias in node.names:
            if alias.name in _OS_PROCESS_CALLS:
                findings.append(Finding(node.lineno, "exec",
                    "'from os import {}' pulls a process-spawn call into scope; "
                    "forbidden in code-fill".format(alias.name)))
            elif alias.name in _OS_ENV_NAMES:
                findings.append(Finding(node.lineno, "env",
                    "'from os import {}' reads the process environment; "
                    "code-fill must not read env/secrets".format(alias.name)))
    return findings


def _collect_bindings(tree: ast.AST):
    """Best-effort module-level binding table for the indirection checks.

    Tracks names bound to the `os` module (`import os as o`) so an aliased
    `o.system()` / `o.environ` is caught like the literal `os.` form, and
    names bound to an absolute-path `Path('/abs')` so a variable-routed
    `p.write_text()` is caught like the inline form. Over-binding fails safe
    (an extra refusal), consistent with this layer's best-effort contract.
    """
    os_aliases = set()
    abs_paths = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    os_aliases.add(alias.asname or "os")
        elif isinstance(node, ast.Assign):
            value = node.value
            if (isinstance(value, ast.Call)
                    and _callee_name(value.func) == "Path" and value.args):
                literal = _string_literal(value.args[0])
                if literal and literal.startswith("/"):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            abs_paths[target.id] = literal
    return os_aliases, abs_paths


def _scan_call(node: ast.Call, os_aliases=frozenset(), abs_paths=None) -> List[Finding]:
    findings: List[Finding] = []
    abs_paths = abs_paths or {}
    func = node.func

    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        obj, attr = func.value.id, func.attr
        is_os = obj == "os" or obj in os_aliases
        if is_os and attr in _OS_PROCESS_CALLS:
            findings.append(Finding(node.lineno, "exec",
                "'{}.{}(...)' spawns or replaces a process; forbidden in "
                "code-fill".format(obj, attr)))
        elif is_os and attr == "getenv":
            findings.append(Finding(node.lineno, "env",
                "'{}.getenv(...)' reads the process environment; code-fill "
                "must not read env/secrets".format(obj)))
        elif obj == "shutil" and attr == "rmtree":
            findings.append(Finding(node.lineno, "escape-fs",
                "'shutil.rmtree(...)' can delete outside the sandbox tree"))

    if isinstance(func, ast.Attribute) and func.attr in _PATH_WRITE_METHODS:
        receiver = func.value
        if isinstance(receiver, ast.Call) and _callee_name(receiver.func) == "Path" and receiver.args:
            literal = _string_literal(receiver.args[0])
            if literal and literal.startswith("/"):
                findings.append(Finding(node.lineno, "escape-fs",
                    "'Path({}).{}(...)' targets an absolute path outside "
                    "the sandbox".format(literal, func.attr)))
        elif isinstance(receiver, ast.Name) and receiver.id in abs_paths:
            findings.append(Finding(node.lineno, "escape-fs",
                "'{}.{}(...)' writes to absolute path {} outside the "
                "sandbox".format(receiver.id, func.attr, abs_paths[receiver.id])))

    if isinstance(func, ast.Name) and func.id in _BUILTIN_EXEC_CALLS:
        findings.append(Finding(node.lineno, "exec",
            "'{}(...)' executes arbitrary code; forbidden in code-fill".format(func.id)))

    if isinstance(func, ast.Name) and func.id == "open" and node.args:
        literal = _string_literal(node.args[0])
        if literal and literal.startswith("/"):
            findings.append(Finding(node.lineno, "escape-fs",
                "'open({}, ...)' targets an absolute path outside the "
                "sandbox -- best-effort: a computed path is not caught".format(literal)))

    return findings


def _scan_python(source: str) -> List[Finding]:
    tree = ast.parse(source)  # SyntaxError propagates -- caller treats as refuse
    os_aliases, abs_paths = _collect_bindings(tree)
    findings: List[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            findings.extend(_scan_import(node))
        elif isinstance(node, ast.Call):
            findings.extend(_scan_call(node, os_aliases, abs_paths))
        elif isinstance(node, ast.Attribute):
            if (node.attr == "environ" and isinstance(node.value, ast.Name)
                    and (node.value.id == "os" or node.value.id in os_aliases)):
                findings.append(Finding(node.lineno, "env",
                    "'{}.environ' reads the process environment; code-fill "
                    "must not read env/secrets".format(node.value.id)))

    findings.sort(key=lambda f: f.line)
    return findings


def _scan_regex_lane(source: str, lang: str) -> List[Finding]:
    """Coarse line-token scan for non-python languages (wave 2).

    Best-effort: no parser, so a token inside a comment or string literal
    still fires. The R9 human gate reading run evidence remains the final
    check for these languages.
    """
    tokens = tuple(_REGEX_COMMON_TOKENS) + _REGEX_LANG_TOKENS.get(lang, ())
    findings: List[Finding] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for token in tokens:
            if token in line:
                findings.append(Finding(lineno, "regex-lane",
                    "line contains '{}' -- best-effort regex match; the R9 "
                    "human gate remains the final check".format(token)))
    return findings


def scan_source(source: str, lang: str = "python") -> List[Finding]:
    """Scan `source` for denylisted constructs. Empty list == clean.

    lang="python" uses the AST lane (SyntaxError propagates on unparseable
    source -- the caller/CLI treats that as a refusal, not a clean pass).
    Any other lang uses the coarser regex lane.
    """
    if lang == "python":
        return _scan_python(source)
    return _scan_regex_lane(source, lang)


_LANG_BY_SUFFIX = {
    ".py": "python", ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
    ".go": "go", ".rs": "rust",
}


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: sandbox_denylist.py <file...>", file=sys.stderr)
        return 2

    had_refuse = False
    had_finding = False
    for arg in argv:
        path = Path(arg)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # Unreadable code cannot run, so it never reaches the sandbox -- fold
            # it into the same exit-2 refusal as a parse error, never let it
            # crash out or collide with the exit-1 "finding" code.
            had_refuse = True
            print("{}: cannot read: {}".format(arg, exc), file=sys.stderr)
            continue
        lang = _LANG_BY_SUFFIX.get(path.suffix, "python")
        try:
            findings = scan_source(source, lang=lang)
        except SyntaxError as exc:
            had_refuse = True
            print("{}: syntax error: {}".format(arg, exc), file=sys.stderr)
            continue
        for finding in findings:
            had_finding = True
            print("{}:{}: {}: {}".format(arg, finding.line, finding.code, finding.message))

    if had_refuse:
        return 2
    if had_finding:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
