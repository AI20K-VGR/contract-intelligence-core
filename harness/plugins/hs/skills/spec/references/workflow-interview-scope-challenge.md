# Workflow — Interview & Generate — Scope Challenge

Split from [workflow-interview.md](workflow-interview.md) (reference size cap) — same doc/authority, only location moved.

## Scope Challenge (always-on, once per PRD, BEFORE decomposition)

Before breaking a PRD into epics/stories, ask the PO **one coarse boundary question** and **lock the answer**. This sets the high-level intent for the whole feature-area so later additions are deliberate, not creep. It runs once per PRD — the first time that PRD is decomposed — and the lock is recorded so it is never re-asked.

This is the **coarse** boundary lock. It is NOT the per-requirement MoSCoW gate (that runs later, at `P4`, and assigns each requirement Must/Should/Could/Won't). Division of labour:

- **Scope Challenge** owns the *boundary*: how much of this feature-area are we building this round — the trimmed core, the whole thing, or just enough to test the idea? Answered once, locked.
- **MoSCoW gate** then *operationalizes* that boundary per requirement, and must stay **consistent** with it. The MUST set must not exceed the locked scope.

**Never re-ask "what's the MVP"** — the Scope Challenge owns the boundary; MoSCoW derives the per-requirement detail from it. Asking both would double-ask the PO (no double-ask).

### Ask (EN | VI)

- **EN:** "Before we break '{PRD title}' into pieces — how much of it are we building this round? **MVP** (the trimmed must-have core), **Full** (the complete feature as you picture it), or **Strip** (a bare slice just to test whether anyone wants it)?"
- **VI:** "Trước khi chia '{tên PRD}' thành các phần — đợt này ta làm tới đâu? **MVP** (phần lõi bắt buộc, tối giản), **Full** (toàn bộ tính năng như bạn hình dung), hay **Strip** (lát mỏng nhất để thử xem có ai cần không)?"

Present this as a 3-option `AskUserQuestion` (MVP / Full / Strip). Keep it terse — one question, one answer.

### Complexity-smell follow-up

If the PRD already looks heavy (the PO has named many sub-features, or the brain-dump for this area is large), add one sentence after the choice: *"This looks like a lot for one round — anything here you'd be comfortable pushing to a later round?"* Record any deferral; do not push the PO.

### Lock + record

- Record the choice on the PRD as `scope_intent: mvp | full | strip` (frontmatter is the source-of-truth). Once set, the Scope Challenge does **not** re-ask on later edits of that PRD.
- A PO who explicitly says "skip the scope question, just decompose" may bypass it — record `scope_intent` as unset and note the bypass in the session log; do not nag.

### Surface out-of-mode additions (never silently add)

After the lock, if the PO (or the brain-dump) adds something clearly **beyond** the locked intent — e.g. a gold-plated extra under a `strip` or `mvp` lock — do not silently fold it in.
Surface it: *"You locked '{PRD}' as {scope_intent} this round, but '{addition}' looks like it goes past that. Add it anyway (and widen the lock), defer it to a later round, or drop it?"* The PO decides.
The MoSCoW gate also flags when the MUST set exceeds the locked scope (consistency check), so the two gates reinforce — they never duplicate the question.

