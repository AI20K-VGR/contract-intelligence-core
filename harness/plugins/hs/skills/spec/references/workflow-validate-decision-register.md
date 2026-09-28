# Workflow — Validate / Approve / Summary — Decision Register Wiring

Split from [workflow-validate.md](workflow-validate.md) (reference size cap) — same doc/authority, only location moved.

### Decision Register wiring (kill re-litigation)

The per-workspace DEC ledger (`docs/product/decisions.md`, allocated by `scripts/dec_ledger.py` — full mechanism + CLI in `references/dec-ledger.md`) is the authoritative, append-only home for explicit PO rulings (`DEC-<n>`). It bookends the keep/change/hybrid flow above: **read it FIRST, write it on resolve.**

**Before surfacing the keep/change/hybrid options — read the ledger first.** A contradiction the PO has *already ruled on* must not be re-asked:

```bash
python3 scripts/dec_ledger.py --root <root> --list
```

The script returns the ledger's blocks (id, status, date, and the rest of the parsed frontmatter) — deterministic parse, no judgment (Script-vs-LLM split). The LLM then judges whether any existing `DEC-<n>` already covers *this* contradiction (same artifacts, same tension). If a matching decision exists, **surface it instead of re-asking**:

> "You already decided this in **DEC-n** ("…title…", because …rationale…). Keep that ruling, or record a new one that supersedes it?"

- **Keep the prior ruling** → no new contradiction is raised; note the `DEC-n` reference and move on (re-litigation avoided).
- **Record a new ruling** → proceed to the keep/change/hybrid options below, then append a new `DEC-<n>` whose body prose names the prior id it revisits. `dec_ledger.py` is append-only with no supersede mechanism — it never flips an old block's `status`, so "supersede" here means a fresh block that says so in its own prose, not a script-managed `status: superseded` flip.

If no existing DEC matches, run the keep/change/hybrid options as normal.

**On resolve (Keep / Change / Hybrid) — append a new `DEC`.** Every resolution of a contradiction is a binding PO ruling, so record it so the same tension cannot resurface unflagged. Allocate and append in one call (the LLM supplies the title + rationale prose; the script owns the id grammar + append-only write through the soft fence + flock):

```bash
python3 scripts/dec_ledger.py --root <root> --add \
  --status active --affects "<approved-artifact-id>" \
  --title "<short ruling>" --body "<why the PO chose Keep/Change/Hybrid>"
```

- **Keep** → the new DEC records "kept the approved version, rejected the new claim" + the why.
- **Change** → the DEC records the switch; the affected artifact would then be **re-approved** via `--approve` — but `--approve` is not a flag hs:spec exposes in this build (see `workflow-validate.md`'s caveat), so today the re-approval promotion is a manual frontmatter edit, not a scripted flow. The engine still never auto-flips — the DEC is the audit trail regardless.
- **Hybrid** → the DEC records both positions + the follow-up to reconcile.

This is the SAME ledger the `--decision` flag writes (it lets the PO log a standalone ruling) — `decisions.md` is the authoritative home for the ruling; other surfaces link to it by id, never copy the rationale (DRY).

**DRY guard:** a `DEC` record holds the ruling + its rationale + ID links (`affects:`) ONLY. It NEVER copies a structural fact that already has a home (a persona narrative in `vision.md`, a goal in `brd.md`, a scope/AC in the PRD/story). Point at those by ID; do not duplicate them.
