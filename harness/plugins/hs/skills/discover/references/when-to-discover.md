# When to discover — when to use hs:discover

Load this drawer in step 1 of hs:discover when the problem may not be clear enough, or when the user asks "do I need to discover?"

## Signs that hs:discover SHOULD run

| Sign | Reason |
|---|---|
| Problem described by expected outcome, not by solution | Must frame before planning |
| >=2 fundamentally different approaches exist | Diverge + critique needed |
| Prior art or existing codebase solutions are unknown | hs:research needed |
| Technical constraints are unclear (performance? security? backward-compat?) | Must finalize constraints first |
| Scope may vary significantly depending on the chosen direction | Brief keeps hs:plan on track |
| User says "I want to add X" and X is not yet defined | This is a problem that needs discovery |

## Signs to SKIP hs:discover (go straight to hs:plan)

| Sign | Action |
|---|---|
| Problem has a clear solution confirmed by the user | `/hs:plan <description>` |
| Only one reasonable implementation exists (bug fix, typo, config change) | `/hs:plan` or `/hs:cook` directly |
| A brief already exists in `plans/` from a previous session | Reuse it, do not re-discover |
| User has already brainstormed outside this channel and only needs a plan | `/hs:plan <brainstorm result>` |

## When to use --quick instead of the full chain

`--quick` is appropriate when:
- The problem is small, low-risk, 1-2 days to implement
- The user has a clear mental model and only needs a quick sanity check
- No open technical questions require research

Do not use `--quick` when:
- Trade-offs involve security, performance, or backward compatibility
- Library or technology comparisons with external sources are needed
- Scope could blow up if the wrong direction is chosen

## Scoping questions (step 1)

If the input is ambiguous on >=2 dimensions, ask via `AskUserQuestion`:

1. **What is the problem?** — describe it by behavior, not by solution
2. **Who is affected?** — end user / dev / CI / infra?
3. **Hard constraints?** — what cannot be negotiated
4. **What does done look like?** — preliminary acceptance criteria
5. **Timeline / urgency?** — affects --quick vs full chain

If >=3 items have no answer -> do not proceed with discovery, ask first.

## When discovery is blocked

Trigger: after diverge there are still not >=2 distinct directions, or after critique every option is Rejected with no alternative.

Steps to handle:
1. Call `hs:problem-solving` with a specific description of where the block is
2. Do not invent options — wait for problem-solving to return a reframe
3. If problem-solving also cannot resolve it -> escalate to the user via
   `AskUserQuestion`: present the block, propose narrowing scope or stopping discovery

## Brief scope boundaries

Brief is a map for hs:plan to create a plan — it is not a plan itself. Signs the brief is creeping into plan territory:

- Brief has specific implementation steps (class names, detailed file paths)
- Brief has per-task timelines or estimates
- Brief has test cases

When this happens -> stop, move the content into "Explicitly OUT of scope" or record it via `backlog_register.py add`, do not pack it into the brief.
