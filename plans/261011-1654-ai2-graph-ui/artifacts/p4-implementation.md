# P4 implementation notes

## Changes

- Added an AI2 processing timeline that renders only Backend trace stage/status/timing/count/reason fields. Complete, running, interrupted, incomplete and unavailable outcomes have separate text; no success is inferred from missing stages or empty counts.
- Added relation list, selected-relation inspector and evidence actions that forward opaque citation references to the caller. Rows expose direction, label, review state and source/target node labels; callers can map IDs to dossier clause addresses without guessing.
- Added paged relation state with stable-ID deduplication, count-aware completion, retry after request errors, stale-scope rejection and a repeated-cursor stop condition. A non-ready persistence state and verified empty graph render differently.
- Kept the relation list as a responsive, keyboard-operable primary view with native buttons, visible focus, text status labels and no fixed minimum canvas width. Page integration remains in P5 as planned.

## Verification evidence

- Red run: new component test failed with `Cannot find module './ProcessingTimeline'` before implementation.
- Focused graph views: `npm test -- --run src/components/ai2-graph/ai2GraphViews.test.tsx` — 6 passed.
- Full Frontend suite: `npm test -- --run` — 124 passed across 35 files.
- `npx tsc -b --pretty false` — passed.
- `npm run lint` — 0 errors, 13 existing warnings outside the new AI2 graph components.
- `npm run build` — passed; existing bundle-size warning for chunks above 500 KB.

## Gate status

P4 component and regression checks pass. Responsive layout is implemented with wrapping and `min-w-0`, and interactive controls use native keyboard-focusable buttons. A real 320 CSS px browser/manual check is still part of P5 page integration and has not yet been claimed here. Runtime feature flags remain OFF.
