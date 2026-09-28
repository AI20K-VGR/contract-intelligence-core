# when-stuck — flowchart dispatch

Use when block type is unclear. Match symptoms to a technique.

## Flowchart

```
STUCK
│
├─ Complexity escalating? Same thing 5+ ways? Special cases growing?
│  └─→ simplification-cascades.md
│
├─ Conventional solutions not enough? Breakthrough needed?
│  └─→ collision-zone-thinking.md
│
├─ Same problem recurring in many places? Reinventing wheels?
│  └─→ meta-pattern-recognition.md
│
├─ Solution feels forced? "There is only one way"?
│  └─→ inversion-exercise.md
│
├─ Not sure it will scale? Edge cases unclear?
│  └─→ scale-game.md
│
└─ Broken code / failing test / wrong behavior?
   └─→ hs:debug (not this skill)
```

For symptom -> technique mapping (which reference file to open), see SKILL.md's Quick dispatch table — single source; this flowchart only branches by symptom class.

## When no technique resolves the block

1. **Reframe the problem** — is the right problem being solved?
2. **Reduce scope** — solve a smaller version first
3. **Question constraints** — are the constraints real or assumed?
4. **Combine techniques** — see Combinations table in SKILL.md
5. **Escalate** — use `hs:brainstorm` to explore multiple directions with an agent
