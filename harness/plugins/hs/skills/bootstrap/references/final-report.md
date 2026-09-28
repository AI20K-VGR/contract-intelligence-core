# Bootstrap completion report

Load this file after `hs:cook` completes.

## Report structure

1. **Changes summary** -- short bullets, favor brevity over grammar:
   - Files/dirs created
   - Conventions established
   - Remaining gaps (if any)

2. **Getting started (onboarding)**
   - First commands to run
   - Required environment variables / config
   - Ask one question at a time if user input is needed (API key, etc.)

3. **Open questions** -- list if any; do not fabricate if there are none.

4. **Suggested next steps**
   - `hs:plan` if another feature is needed
   - `hs:docs` if documentation needs expanding
   - `hs:project-management` to track progress

## Commit / push

Ask the user: do they want to commit and push?
- Yes -> `hs:git-manager` agent commits (and pushes if requested).
- No -> stop; do not auto-commit.

`--fast` mode: keep this gate -- it does not mean auto-commit.

## Journal

After completion (commit or not), call `hs:journal` to record the session.

## Presentation rules

- Favor brevity over grammar.
- Do not repeat content already in the plan.
- Do not create a separate report file -- present directly in the session.
