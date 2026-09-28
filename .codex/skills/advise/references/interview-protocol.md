# Interview protocol (hs:advise, Step 3)

The interview is the core of `hs:advise`. Ground it in scout findings when they exist; a
question grounded in code beats an abstract one.

## HARD-GATE-ONE-QUESTION

Ask exactly ONE question per `AskUserQuestion` call (or per relay turn). Never batch multiple
questions — asking several at once is bewildering and produces shallow answers. Wait for the
answer, then decide the next question from it.

## The progression

Grill the user, in this order:

1. **Start with why** — what outcome makes this worth doing? What breaks or is lost if it is
   never done?
2. **Challenge with pros & cons** — present the strongest argument against their current
   framing and ask them to respond to it.
3. **Explore alternatives** — surface 2-3 different ways to reach the same outcome (including
   "do nothing" or "do less") and ask which trade-offs they can live with.
4. **Pressure-test constraints** — budget, timeline, maintenance burden, skills available,
   existing stack lock-in.
5. **Converge** — keep looping until you can restate the problem as exact requirements and
   goals in the user's own terms.

## Rules

- Ground options in scout findings when they exist (e.g. "your adapter layer already does X —
  extend it, or bypass it?").
- Be direct and skeptical, never hostile. Push back on vague answers ("make it better" is not a
  requirement).
- Stop interviewing when answers stop changing the reframing — typically 4-8 questions. Do not
  pad.
- **The decisions are the user's.** Challenge hard, then respect the call. Never override an
  explicit user decision in the final advice; record disagreement as a noted trade-off instead.

## Confirm the reframing (Step 4)

Before advising, present and get explicit confirmation of:

- **Problem (reframed)** — one paragraph in concrete terms
- **Exact requirements** — numbered, verifiable
- **Goals** — what success looks like, measurable where possible
- **Non-goals** — what is explicitly out of scope
- **Constraints** — non-negotiables captured during the interview

If the user corrects anything, update and re-confirm. Do not advise on an unconfirmed
reframing.
