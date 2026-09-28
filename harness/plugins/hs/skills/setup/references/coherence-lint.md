# Coherence lint — warn on a config that fights itself (per-step + final)

Setup's job: not only write values, but catch a config internally incoherent or mismatched to the user. Run this lint TWICE: a quick per-step check right after each group is written, and a holistic pass at the very end (Full mode) consolidating every mismatch. Warn and ASK — never silently "correct" a deliberate choice. Frame each as: *"you chose X together with Y
— that pairing usually means Z; intended?"*. A confirmed mismatch is left as-is (user decisions hold); the lint only surfaces, it does not overrule.

Apply these checks (extend as new knobs land):

**Posture ↔ strictness (solo / team):**
- solo + `thorough`/`ship-grade` as the DEFAULT review, OR a team-grade DoD (integration + coverage on every feature), OR guard preset `strict` → **too strict for solo**: daily friction with no second pair of eyes to justify it. Suggest light-default review + solo-lean DoD, deep on-demand.
- team + lean DoD (unit-only, no coverage floor) + `allow_self_review:true` + empty `protected-branches` → **too loose for a team**: nothing independent gates a merge. Suggest a coverage floor, real reviewers, and protecting the main branch.
- solo posture flipped but guard/stage left at team values (or vice-versa) → **posture split-brain**: the human-friction layer and the gate layer disagree.

**Audience / expertise ↔ depth (output + voice):**
- `audience` low (0–1, non-technical prose) together with `code_style` high (4–5) or an expert/blunt voice (`persona=reality-check`, high `voice_level`) → **split reader model**: reports aimed at a beginner but code/terminal aimed at an expert. Legit when the AUTHOR is expert but the report READERS are not — so confirm intent, do not assume error.
- `audience` high (4–5, dense expert prose) with a learner persona or low `voice_level` → **too deep for the stated reader**.
- an expert profile (dev-working/dev-expert archetype, deep rigor) but everything shallow (audience 0, code_style 0, review light, `interview_rigor=light`) → **too shallow for the experience level**; likely to read as patronizing.

**Voice internal consistency:**
- high `voice_level` (6–9, wants challenge) with `interview_rigor=light` + `action_prompting=minimal`
  → contradictory: asked for bluntness but told not to probe or suggest.

The final pass prints ONE consolidated list (file · chosen value · why it looks off · the fitting alternative) and asks which, if any, to revisit. If nothing is off, say so in one line and move on.
