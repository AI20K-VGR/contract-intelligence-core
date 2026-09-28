# Layer-0 archetype onboarding — presets

Present the 10 archetypes from `"${HARNESS_BIN_ROOT:-.}"/harness/data/voice-presets.yaml` as a numbered list and ask "which best describes you?". The user enters a number or picks "I'll configure manually" to skip to Layer-1. After applying a preset, **always ask "adjust anything? [keep / fine-tune]"** — preset is a seed, not a lock (the refinement path is mandatory).

Load and display presets with:
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/voice_presets.py list
```

Apply a preset (all-or-nothing — validates all axes before writing either file):
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/voice_presets.py apply <number>
```

After applying, proceed to Layer-0.6, then Layer-1 if the user says "fine-tune".
