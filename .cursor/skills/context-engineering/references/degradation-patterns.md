# Context degradation patterns — diagnostic taxonomy

Quality degrades as context grows — a continuum, not a binary cliff. The SKILL covers the *mitigation* (place critical info at start/end, compact at ≥70%). This drawer is the *diagnostic*: name the failure mode so the fix is targeted, not "add more tokens".

| Pattern | Cause | How it shows up |
|---|---|---|
| **Lost-in-Middle** | U-shaped attention — start and end dominate | Recall of mid-context facts drops sharply; the model "forgets" a requirement it was given |
| **Context Poisoning** | An error enters and is then referenced as truth | A hallucination persists despite correction; the model keeps building on a wrong fact |
| **Context Distraction** | Irrelevant material crowds out the task | One strong distractor derails reasoning; output drifts off-task |
| **Context Confusion** | Several tasks/threads mixed in one window | Wrong tool calls; requirements from task A leak into task B |
| **Context Clash** | Contradictory facts both present | Inconsistent reasoning; output flips between two conflicting premises |

## Targeted fixes

- **Lost-in-Middle** → move decisions/constraints/acceptance criteria to the start or end; never bury the live requirement in the middle. (Already the SKILL's placement rule.)
- **Poisoning** → when a fact is corrected, do not just append the correction — excise or clearly supersede the poisoned text, or it keeps getting referenced. A fresh subagent with a clean window is the strongest reset.
- **Distraction** → drop settled tool output and old debate; load only what the current step needs (`references/what-to-load-when.md`).
- **Confusion** → one task per window; split parallel/unrelated work into isolated subagents (`references/subagent-delegation.md`), each with minimal context.
- **Clash** → reconcile or delete the older premise explicitly; do not leave both versions for the model to pick from.

## When to reach for this

Reasoning quality dropped but the task did not get harder, the model repeats a mistake after correction, or it mixes up which task it is on — match the symptom to a pattern above and apply that fix instead of growing the window.
