## Tips for Better Results

### Query Strategy

- Use **multi-dimensional keywords** — combine product + industry + tone + density: `"entertainment social vibrant content-dense"` not just `"app"`
- Try different keywords for the same need: `"playful neon"` → `"vibrant dark"` → `"content-first minimal"`
- Use `--design-system` first for full recommendations, then `--domain` to deep-dive any uncertain dimension
- Always add `--stack react-native` for implementation guidance

### Common Sticking Points

| Problem | What to Do |
|---------|------------|
| Can't decide on style/color | Re-run `--design-system` with different keywords |
| Dark mode contrast issues | Quick Reference §6 (quick-reference.md): `color-dark-mode` + `color-accessible-pairs` |
| Animations feel unnatural | Quick Reference §7 (quick-reference.md): `spring-physics` + `easing` + `exit-faster-than-enter` |
| Form UX is poor | Quick Reference §8 (quick-reference-forms-nav-data.md): `inline-validation` + `error-clarity` + `focus-management` |
| Navigation feels confusing | Quick Reference §9 (quick-reference-forms-nav-data.md): `nav-hierarchy` + `bottom-nav-limit` + `back-behavior` |
| Layout breaks on small screens | Quick Reference §5 (quick-reference.md): `mobile-first` + `breakpoint-consistency` |
| Performance / jank | Quick Reference §3 (quick-reference.md): `virtualize-lists` + `main-thread-budget` + `debounce-throttle` |

### Pre-Delivery Checklist

- Run `--domain ux "animation accessibility z-index loading"` as a UX validation pass before implementation
- Run through Quick Reference **§1–§3** (quick-reference.md, CRITICAL + HIGH) as a final review
- Test on 375px (small phone) and landscape orientation
- Verify behavior with **reduced-motion** enabled and **Dynamic Type** at largest size
- Check dark mode contrast independently (don't assume light mode values work)
- Confirm all touch targets ≥44pt and no content hidden behind safe areas

---

