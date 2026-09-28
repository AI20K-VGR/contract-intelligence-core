# harness/standards/ — structured standards tree (prose lives in `docs/`)

The two **prose** standards files are single-sourced in `docs/` — one home, no aliases:

```
docs/system-architecture.md   # system architecture the team follows
docs/code-standards.md        # shared code discipline (naming, testing, commits, ...)
```

Every consumer reads them straight from `docs/`: `hs:plan` and `hs:cook` (Step 0),
`scaffold_standards.py` (writes the TBD skeleton there), and the installer's
`_check_standards`. There is no `harness/standards/` copy or symlink of these two — that
directory holds the structured tree below, not the prose pair.

The harness multi-user model: **one developer per machine, one clone, one harness** — no one
shares files with anyone else. What keeps everyone moving in the same direction is these two
standards files: hs:plan and hs:cook READ them before working, so plans and code on every
machine follow the same architecture and the same discipline.

**If these two files don't exist yet, run `/hs:docs`** — it authors them (and the rest of
the `docs/` set) from the codebase. For a bare section-header skeleton to fill by hand,
`python3 harness/scripts/scaffold_standards.py --type <system-architecture|code-standards>`
writes the `> TBD` template into `docs/`. The harness reminds you at session start (the
`setup_nudge` SessionStart hook) and at install time (`_check_standards`) whenever either
file is missing or thin; `hs:plan` also stops and prompts before planning on an empty base.

## Structured standards tree

Beyond the two prose files above, the harness reads a structured standards tree to build the graph `rule → rule-group → STD-area → ARCH-goal → vision` (same shape as the product-spec graph, renamed to the standards domain). This tree genuinely lives in `harness/standards/`. Flat layout:

```
harness/standards/
  vision.md                 # Engineering Vision (singleton, id VISION)
  STACK.md                  # tech-stack facts (singleton, id STACK)
  charter.md                # Architecture Charter — ARCH-G<n> goals, metrics REQUIRED
  areas/
    STD-<AREA>.std.yaml     # 1 file per standard area; rule-groups + rules declared
                            # inline (id STD-<AREA>-RG<n>-R<n>)
  templates/                # skeleton templates for generate_standards_templates.py
  .snapshots/               # graph snapshots (machine-written, gitignored)
```

The `vision`/`STACK`/`charter`/`areas` files in this tree are per-machine input (gitignored like all other standards); only `templates/` and `README.md` are tracked.

Generate an artifact quickly via the generator (assigns parent-scoped id + renders tokens):

```bash
python3 harness/scripts/generate_standards_templates.py \
  --root . --type std_area --slug AUTH --write
```

Check the standards tree for consistency (dangling/orphan/cycle) — CI runs this automatically:

```bash
python3 harness/scripts/standards_strict_gate.py --root .   # exit 2 on error
```

The DEC ledger (`docs/decisions.md`) is also per-clone: sync + deduplicate numbers via git MR like any other tracked file (DEC number collision between two branches → renumber at MR).
