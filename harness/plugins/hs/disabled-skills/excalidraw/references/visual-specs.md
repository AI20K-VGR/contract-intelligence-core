# excalidraw — visual specs (sizing + aesthetics)

Lookup tables for generating the JSON (workflow step 3).

## Sizing rules

Err on the side of too much space — tight spacing is mistake #1.

| Property | Value |
|---|---|
| Box width | 200-240px |
| Box height | 120-160px |
| Gap (labeled arrows) | 150-200px |
| Gap (unlabeled arrows) | 100-120px |
| Row spacing | 280-350px |
| Font (labels) | 16px |
| Font (titles) | 20-24px |

## Aesthetics

- `roughness: 0` default (clean/modern); `1` if hand-drawn is needed
- `strokeWidth: 2` standard; `1` subtle; `3` emphasis
- `opacity: 100` always — use color/size for hierarchy, not transparency
- `fontFamily: 3` (monospace) — canonical attribute table: `json-schema.md`
- Arrow label: `strokeStyle: "dashed"` for async; `"dotted"` for weak deps
