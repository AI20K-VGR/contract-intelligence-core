# Handoff & Critique Gate

Lightweight final gate for UI/build/demo/deck outputs before saying done —
`/hs:frontend-design`, `/hs:show-off`, the slides drawers in this skill. Distinct from
`design-critique-guide.md` (scored 6-dimension rubric for `/hs:design`'s
standalone logo/CIP/banner/social/icon/poster deliverables) and from
`/hs:ui-ux` (upfront rule checklist consulted while building). This
gate is the last check before presenting the result, and the format for
reporting it. Applies once a generated asset is integrated into a frontend
build, demo page, or deck — not to a standalone `/hs:design` deliverable
still under its own critique flow.

## The 5 dimensions

Pass/fail, not scored. For numeric standards (contrast ratio, spacing scale,
font-family cap, touch-target size), defer to `/hs:frontend-design` and
`/hs:ui-ux` rather than restating a number here.

1. **Context fit** — matches the brief, brand, and audience; not a generic
   template that would work unchanged for a different product or client.
2. **Visual hierarchy** — one clear entry point, an intended reading path, no
   competing focal points. Squint test: blur the layout mentally — does the
   hierarchy still read?
3. **Craft/detail** — spacing, alignment, and type are consistent; no rough
   or unfinished edges.
4. **Usability/accessibility** — contrast, focus states, touch targets, and
   responsive behavior meet the standards owned by `/hs:frontend-design` /
   `/hs:ui-ux`; real content is used, not lorem ipsum or CSS scenery.
5. **Implementation safety** — no clipped or overflowing layout, verified
   across the viewports/ratios the task requires, no broken links or missing
   assets, matches the declared theme/preferences.

## Gate rule

Every failing dimension is fixed before handoff. When a fix is out of scope,
too costly for the round, or blocked, it is not shipped silently — name it
under "Known limitations" in the handoff below instead.

## Handoff template

```markdown
## Handoff

**Accepted direction**: [the direction/brief this output committed to]

**Files changed/created**:
- `path/to/file` — [what changed]

**Screenshots/preview path**: [file path or URL where the result can be viewed]

**Validation**: [how the 5 dimensions above were checked — squint test, viewport
sweep, contrast check, etc.]

**Known limitations**: [any dimension that failed and was not fixed, with why —
or "None"]
```
