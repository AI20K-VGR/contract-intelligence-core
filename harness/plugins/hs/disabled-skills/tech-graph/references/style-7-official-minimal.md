# Style 7: Official Minimal

Clean, modern — minimal but precise. White on white, differentiation through border and label only.

## Color Palette

```
Background:     #ffffff  (pure white)
Primary text:   #0d0d0d  (near black)
Secondary text: #6e6e80  (muted gray)
Border:         #e5e5e5  (light gray)

Accent colors (reserved — use sparingly):
  Green:  #10a37f  (primary flow)
  Blue:   #1d4ed8  (links, actions)
  Orange: #f97316  (highlights, warnings)
  Gray:   #71717a  (secondary elements)
```

## Typography

```
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
             'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif
font-size:   16px node labels, 13px descriptions, 12px arrow labels
font-weight: 600 for titles, 500 for labels, 400 for descriptions
letter-spacing: -0.01em (tight)
```

No custom fonts — system font stack only.

## Node Boxes

```xml
<!-- Standard node -->
<rect x="100" y="100" width="180" height="80" rx="8" ry="8"
      fill="#ffffff" stroke="#e5e5e5" stroke-width="1.5"/>

<!-- Accent node (with green left border strip) -->
<rect x="100" y="100" width="180" height="80" rx="8" ry="8"
      fill="#ffffff" stroke="#e5e5e5" stroke-width="1.5"/>
<rect x="100" y="100" width="4" height="80" rx="2" ry="2"
      fill="#10a37f"/>
```

Key techniques: white fill, light gray border, optional 4px left-border accent, rx=8, stroke-width 1.5. No gradients, no shadows.

## Arrows

```xml
<defs>
  <marker id="arrow-oai" markerWidth="10" markerHeight="7"
          refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#71717a"/>
  </marker>
  <marker id="arrow-oai-green" markerWidth="10" markerHeight="7"
          refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#10a37f"/>
  </marker>
</defs>
<!-- Default connection (gray) -->
<line stroke="#71717a" stroke-width="1.5" marker-end="url(#arrow-oai)"/>
<!-- Primary/accent connection (green) -->
<line stroke="#10a37f" stroke-width="1.5" marker-end="url(#arrow-oai-green)"/>
<!-- Optional/async (dashed) -->
<line stroke="#71717a" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrow-oai)"/>
```

Arrow labels: 12px, gray `#6e6e80`, no background rect (white canvas is default), midpoint placement.

## Database Shapes

```xml
<ellipse cx="200" cy="100" rx="50" ry="12" fill="#ffffff" stroke="#e5e5e5" stroke-width="1.5"/>
<path d="M 150,100 L 150,140 Q 200,155 250,140 L 250,100"
      fill="#ffffff" stroke="#e5e5e5" stroke-width="1.5"/>
<ellipse cx="200" cy="140" rx="50" ry="12" fill="none" stroke="#e5e5e5" stroke-width="1.5"/>
```

## Grouping Containers

```xml
<rect x="80" y="80" width="400" height="200" rx="8" ry="8"
      fill="none" stroke="#e5e5e5" stroke-width="1" stroke-dasharray="4,3"/>
<text x="90" y="97" fill="#6e6e80" font-size="12" font-weight="500">Group Label</text>
```

## Layout Principles

- Snap all coordinates to 8px grid
- 100px horizontal spacing, 120px vertical spacing
- 40px+ margins; no decorative elements
- Only use color when semantically meaningful

## SVG Template

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 600" width="960" height="600">
  <style>
    text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif; }
  </style>
  <defs>
    <marker id="arrow-oai" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#71717a"/>
    </marker>
    <marker id="arrow-oai-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#10a37f"/>
    </marker>
  </defs>
  <rect width="960" height="600" fill="#ffffff"/>
  <text x="480" y="30" text-anchor="middle" fill="#0d0d0d"
        font-size="20" font-weight="600">Diagram Title</text>
  <!-- nodes, edges, legend (minimal) -->
</svg>
```
