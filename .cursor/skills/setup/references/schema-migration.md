# Schema migration check (run before Layer-0)

Before presenting archetypes, check the **live** terminal-voice file for pre-split keys. The live file is whatever `voice_prefs.py` resolves — `$HARNESS_TERMINAL_VOICE`, else a gitignored `.harness-dev/terminal-voice.yaml` at the repo root,
else the shipped `"${HARNESS_BIN_ROOT:-.}"/harness/data/terminal-voice.yaml`. Do NOT check only the shipped data file: on a dogfood or dev-override install that file is the neutral
default and is already clean, so checking it (or running a bare `migrate_voice_output.py` dry-run, which also defaults to the shipped file) will falsely report "no legacy / no-op" while the live override still carries the stale keys.

Grep every candidate for the three pre-split keys — `output_style` and `detail_level` (both have read-time shims and migrate-script support, so their values map into the new schema), plus `coding_level` (a hard 2.0.0 rename to `terminal_voice_level` with NO shim and NO migrate support — an old `coding_level` value is silently ignored on load and dropped on save, never carried over):

```bash
for f in "$HARNESS_TERMINAL_VOICE" .harness-dev/terminal-voice.yaml "${HARNESS_BIN_ROOT:-.}"/harness/data/terminal-voice.yaml; do
  [ -f "$f" ] && grep -lE '^\s*(output_style|detail_level|coding_level)\s*:' "$f"
done
```

If a live file carries any of them:

1. Notify the user which file and which keys (e.g. `.harness-dev/terminal-voice.yaml` carries `coding_level` + `detail_level`). `detail_level`/`output_style` are read at load time via shims so the session still works; `coding_level` has no shim — it is already dead (ignored, its value lost to the default). Either way, cleaning the file removes the stale keys.
2. **Canonical fix for the voice file — a CLI re-save, not the migrate script.** A single `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/voice_prefs.py --set persona=<current-value>` does load→merge→save: load resolves `detail_level` into `terminal_voice_level` via its shim, then save writes ONLY known keys —
so all three legacy keys disappear and the header is preserved. Caveat: `coding_level` carries NO value (no
   shim), so re-save just drops it; `terminal_voice_level` keeps whatever it already resolved to. Read current values first (plain `voice_prefs.py`) and re-set a knob to its current value so the write is a value no-op.
3. **Use `migrate_voice_output.py` only for the cross-file `output_style → output.yaml` (`code_style`) move**, and point `--tv` at the live file — its default targets the shipped data file. This script removes `detail_level`/`output_style` but does NOT drop `coding_level`, so finish with the step-2 re-save to fully clean the voice file.
   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/migrate_voice_output.py --tv <live-file> --check     # exit 1 if migration needed, 0 if clean
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/migrate_voice_output.py --tv <live-file> --dry-run   # preview the diff, write nothing
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/migrate_voice_output.py --tv <live-file> --apply     # apply
   ```
   `--check` is the deterministic surfacing probe (exit code = needs-migration); run it first at onboard, and only prompt the user when it signals legacy keys.
4. Propose (do not auto-run); wait for the user's answer. Migration is optional but recommended.

If no candidate file carries a legacy key, skip this block silently and go straight to Layer-0.
