# SVG Technical Diagram Layout Best Practices

## Universal Layout Rules

### 1. Component Spacing
- Minimum clearance between components: 80px (edge to edge)
- Minimum clearance for arrow paths: 60px from component edges
- Layer vertical spacing: 120px between horizontal layers
- Same-layer horizontal spacing: 100–120px between components

### 2. Arrow Routing & Connection Points

#### Connection Point Rules
- Never connect arrows to component corners — use edge midpoints
- Top/bottom edges: `cx ± offset` (offset=0 for single, ±30px for multiple arrows)
- Left/right edges: `cy ± offset`
- Clearance from corners: minimum 20px

#### Arrow Path Routing
- Avoid diagonal lines crossing components — use orthogonal routing (L-shaped paths)
- Curved arrows: control point ≥40px from any component edge
- Multiple arrows between same layers: stagger Y-coordinates by 15–20px

```svg
<!-- Bad: diagonal arrow crosses component -->
<path d="M 200,100 L 600,400"/>

<!-- Good: orthogonal routing around component -->
<path d="M 200,100 L 200,250 L 600,250 L 600,400"/>

<!-- Good: curved with safe control point -->
<path d="M 200,100 Q 400,200 600,400"/>
```

### 3. Arrow Label Placement
- Position: midpoint of arrow path, offset 5–10px perpendicular to arrow direction
- Background rect: include when label sits over another element (fill=canvas bg, opacity 0.9–0.95, padding 4px H / 2px V)
- Safety distance: 15px minimum from any component edge
- Multiple converging arrows: stagger label positions vertically by 20px

### 4. Component Overlap Detection
Before finalizing SVG, verify:
- No component bounding boxes overlap (include safety margin)
- No arrow paths pass through component interiors
- No text labels overlap with components or other labels

### 5. Z-Index Layering (SVG render order, back to front)
1. Background rect
2. Grouping containers (dashed rects)
3. Arrow paths
4. Arrow label background rects
5. Components (boxes, cylinders, etc.)
6. Component text
7. Arrow label text
8. Legend

## Line Overlap Prevention (most common rendering bug)
When two arrows must cross, use jump-over arcs:
- Crossing horizontal arrows: semicircle arc (r=5px, stroke=arrow color, fill=none)
- Multiple crossings: stagger arc radii (5px, 7px, 9px)
- Never let two arrow segments cross without a jump-over arc

## Style-Specific Spacing

### Style 1 Flat Icon
- Snap all coordinates to 8px grid
- rx=8 ry=8 for rounded rects (consistent)
- Arrows: 1.5–2px, no shadows

### Style 6 Official Warm
- Soft shadows: `<feDropShadow dx="0" dy="2" stdDeviation="6" flood-color="#00000008"/>`
- rx=12 ry=12 (more rounded)
- Arrows: 2px, subtle markers

## Validation Checklist
- [ ] No arrow-component overlaps
- [ ] Arrow labels have background rects when needed
- [ ] Minimum 60px clearance for all arrow paths
- [ ] Component spacing ≥80px
- [ ] Arrow connection points avoid corners (≥20px)
- [ ] Multiple arrows between layers are staggered
- [ ] Legend readable and not overlapping content
- [ ] SVG validates with `rsvg-convert`

## Common Anti-Patterns

| Anti-Pattern | Fix |
|--------------|-----|
| Arrow crosses component | Use orthogonal routing |
| Label overlaps component | Add background rect + increase offset |
| Components too close | Increase spacing to 80px minimum |
| Arrow connects to corner | Move connection point to edge midpoint |
| No z-index planning | Follow render order: arrows → components → text |
| Two arrows cross without arc | Add jump-over semicircle arc |
