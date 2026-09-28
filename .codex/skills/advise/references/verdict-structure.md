# Verdict structure (hs:advise, Step 5)

Deliver the final advice in these eight parts. Apply **YAGNI, KISS, DRY** in that order; prefer
boring, proven approaches; flag novelty as risk unless the user's goals demand it.

1. **Verdict** — a one-paragraph honest take. If the idea is weak, over-engineered, or
   premature, say so plainly and why.
2. **What you should do** — concrete, ordered actions serving the confirmed goals.
3. **What you should not do** — traps, premature optimizations, scope creep, approaches that
   look attractive but cost more than they return.
4. **What could be better / more efficient** — cheaper or simpler paths to the same outcome,
   ranked by effort-to-impact.
5. **My take and how to get there** — your recommended path with a step-level route from the
   current state to the goal.
6. **Benefits** — bulleted, tied to the confirmed goals.
7. **Trade-offs** — bulleted, honest costs of the recommendation, including what the user's own
   decisions cost where you disagreed.
8. **Work checklist & success metrics** — the advice MUST end with two concrete lists:
   - *Work checklist* — an ordered checkbox list (`- [ ] ...`) of the actual tasks to execute
     the recommendation, small enough to hand to `hs:plan` or `hs:cook`.
   - *Success metrics* — measurable criteria that define "done" and "working", each verifiable
     by a command, a number, or an observable state, not a vibe. State the target value where
     one exists.
