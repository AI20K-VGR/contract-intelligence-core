#!/usr/bin/env python3
"""memory_index_check.py — the memory index is reachable, alive and under its ceiling.

`MEMORY.md` is loaded into every session's context, and it is a SHARED file: six
lanes on this project resolve to the same `~/.claude/projects/<slug>/memory/`
directory. There is no git there, no lock, and no review — a lane that rewrites
the file wholesale silently discards what another lane wrote a minute earlier.

── THE CEILING IS TWO NUMBERS, AND ONE OF THEM IS NOT BYTES ───────────────────
The loader refuses past **200 lines** OR **~24985 CHARACTERS**, and says which
one broke. `wc -c` measures a THIRD quantity: this directory's Vietnamese text
runs ~13 % larger in bytes than in characters (measured `260908`: 27354 bytes for
24334 characters), so a gate keyed on bytes cuts blind and cuts early. That
mistake has been made twice here; `len(text)` is the measurement, and this gate
prints both so the next reader can see them differ.

── WHY REACHABILITY, NOT JUST THE CEILING ─────────────────────────────────────
Trimming the index is what keeps it under the ceiling, and trimming is exactly
what drops a memory out of recall. A file nothing points at still exists on disk
and is never read again — it fails silently, in the direction of "everything
looks fine". So the ceiling and reachability have to be one gate: satisfying the
first by breaking the second is the obvious move and the wrong one.

Two tiers: `MEMORY.md` names cluster files, a cluster file names its members.
Every memory must be reachable in at most two steps.

── WHY `[[wikilink]]`S ARE SCORED SEPARATELY ──────────────────────────────────
They are the cross-references INSIDE memories, not the index. Nothing has ever
checked them: measured `260908`, 1098 wikilinks with 2 genuinely dead (one
carrying a stray `.md` suffix, one naming a file that was renamed).

🛑 A naive `\\[\\[([^\\]]+)\\]\\]` scan reports 6, and 4 of those are FALSE: `[[..]]`,
`[[...]]`, `[[x]]` are placeholders written inside prose, and `[[:space:]]` is a
POSIX character class quoted from a real grep command. A gate that reds on those
teaches people to edit correct prose, so they are excluded by name — a list that
is deliberately short and explicit rather than a clever pattern.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: The loader's two limits. Neither is a byte count.
_MAX_LINES = 200
_MAX_CHARS = 24985

#: Where the gate starts SPEAKING, well before it starts refusing. Measured `260908`: the index was
#: migrated to two tiers at 193 lines and was back to 198 within the hour — four lanes added rows to
#: tier one because nothing told them not to. The ceiling check cannot teach that: by the time it
#: fires the index is already truncating, and whoever trips it is not whoever caused it.
#:
#: 185/23000 leaves roughly fifteen rows of warning. The gap is deliberate — a warning that lands
#: one row before the wall is a warning nobody can act on.
_WARN_LINES = 185
_WARN_CHARS = 23000

#: Placeholders and quoted syntax that LOOK like wikilinks. Explicit, not clever:
#: a pattern smart enough to exclude these would also exclude real typos.
_NOT_WIKILINKS = frozenset({"..", "...", "x", ":space:", "name", "their-name"})

#: 🛑 The label is NOT `[^\]]*`. Measured `260908`: the row for
#: `thu-thuat-ngoac-khong-di-qua-ssh.md` is labelled ``[thủ thuật `[p]` không qua ssh]`` — a
#: bracket inside the label — and the naive class stops at it, so the link is never seen and the
#: file reads as an orphan. Non-greedy up to the first `](` is what markdown actually means here.
_LINK = re.compile(r"\[.*?\]\(([^)]+\.md)\)")
_WIKI = re.compile(r"\[\[([^\]]+)\]\]")


def _is_cluster(path: Path) -> bool:
    """True when this file is a second-tier INDEX, judged by content — never by name.

    🛑 The prefix `cum-` does not mean "cluster". Two memories predate this scheme and start with
    it by coincidence: `cum-trung-lap-la-nhieu-ho` ("a duplicate cluster is several families") and
    `cum-tu-giong-nhau-nua-lat-nua-khong` ("similar phrases, half flipped") are about clusters, and
    a name-keyed check reads them as empty indexes. Measured `260908`: both carry
    `type: feedback` and 0 `.md` links in the body, while every real cluster file carries
    `type: reference` and at least one member.

    Both signals are required, and that is the point rather than belt-and-braces: `type: reference`
    alone would promote any pointer-style memory into a tier of the index, and "has a link" alone
    would promote any memory that cites a neighbour. An index is a file whose JOB is to list, and
    it says so twice.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    head = text.split("---", 2)[1] if text.startswith("---") else ""
    return "type: reference" in head and bool(_LINK.search(text.split("---", 2)[-1]))


def _cluster_files(index_text: str, memory_dir: Path) -> set[str]:
    """Files the index points at that are themselves indexes."""
    return {
        target
        for target in _LINK.findall(index_text)
        if _is_cluster(memory_dir / target)
    }


def warnings(memory_dir: Path) -> list[str]:
    """Lines to say while the index is still legal but heading for the wall.

    Separate from `check` on purpose, and never merged into it: a warning that shares a return
    value with a failure eventually gets treated as one, and a gate that reds on "nearly full"
    teaches people to trim rather than to file. These are advisory and carry no exit code.
    """
    index = memory_dir / "MEMORY.md"
    if not index.is_file():
        return []
    text = index.read_text(encoding="utf-8")
    lines, chars = text.count("\n"), len(text)
    if lines < _WARN_LINES and chars < _WARN_CHARS:
        return []
    return [
        f"MEMORY.md is at {lines}/{_MAX_LINES} lines and {chars}/{_MAX_CHARS} characters — "
        "approaching the loader's ceiling, past which the tail of the index is dropped SILENTLY "
        "and the memories that vanish are the newest ones.",
        "File the next memory in a cluster (`cum-*.md`), not in tier one: a cluster member costs "
        "0 lines of the index. Adding a row here costs one, and there are few left.",
    ]


def check(memory_dir: Path) -> list[str]:
    """Every failure, as a list of lines. Empty means clean."""
    problems: list[str] = []
    index = memory_dir / "MEMORY.md"
    if not index.is_file():
        return [f"no MEMORY.md under {memory_dir} — this gate measured nothing"]

    text = index.read_text(encoding="utf-8")
    n_chars, n_lines = len(text), text.count("\n")
    n_bytes = index.stat().st_size
    if n_lines > _MAX_LINES:
        problems.append(f"MEMORY.md is {n_lines} lines, over the {_MAX_LINES}-line limit")
    if n_chars > _MAX_CHARS:
        problems.append(
            f"MEMORY.md is {n_chars} characters, over the {_MAX_CHARS} limit "
            f"({n_bytes} bytes — a different quantity, do not trim against it)"
        )

    on_disk = {f.name for f in memory_dir.glob("*.md")} - {"MEMORY.md"}
    tier1 = set(_LINK.findall(text))
    tier2: set[str] = set()
    for cluster in _cluster_files(text, memory_dir):
        path = memory_dir / cluster
        if path.is_file():
            tier2 |= set(_LINK.findall(path.read_text(encoding="utf-8")))

    dead = sorted(target for target in tier1 | tier2 if not (memory_dir / target).is_file())
    if dead:
        problems.append(f"{len(dead)} index link(s) name a file that does not exist: {dead[:8]}")

    orphans = sorted(on_disk - tier1 - tier2)
    if orphans:
        problems.append(
            f"{len(orphans)} memory file(s) are reachable from no index and will never be "
            f"recalled again: {orphans[:8]}"
        )

    stems = {f.stem for f in memory_dir.glob("*.md")}
    dead_wiki: dict[str, str] = {}
    for source in sorted(memory_dir.glob("*.md")):
        for target in _WIKI.findall(source.read_text(encoding="utf-8")):
            if target not in stems and target not in _NOT_WIKILINKS:
                dead_wiki.setdefault(target, source.name)
    if dead_wiki:
        listed = ", ".join(f"[[{k}]] in {v}" for k, v in sorted(dead_wiki.items())[:6])
        problems.append(f"{len(dead_wiki)} dead wikilink(s): {listed}")

    return problems


def main(argv: list[str]) -> int:
    memory_dir = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    problems = check(memory_dir)
    index = memory_dir / "MEMORY.md"
    if index.is_file():
        text = index.read_text(encoding="utf-8")
        print(
            f"[memory-index] {text.count(chr(10))}/{_MAX_LINES} lines · "
            f"{len(text)}/{_MAX_CHARS} chars ({index.stat().st_size} bytes) · "
            f"{len(list(memory_dir.glob('*.md'))) - 1} memories"
        )
    for note in warnings(memory_dir):
        print(f"[memory-index] ⚠️ {note}")
    for problem in problems:
        print(f"[memory-index] {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
