# Style 8: Dark Luxury (AI-authored)

Deep black canvas, warm champagne-gold accents, hybrid serif/sans typography. Premium editorial — closest peer Style 2 (Dark Terminal), warmer. Hand-craft SVG directly; do not use the template generator.

## Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0a0a0a` | Canvas fill (deepest black) |
| Surface | `#111111` | Node / panel fill |
| Elevated | `#1a1a1a` | Secondary panels, sub-headers |
| Accent gold | `#d4a574` | Primary arrows, titles, borders, cluster containers |
| Accent dim | `#c9a96e` | Muted gold borders, secondary accents, cluster labels |
| Accent bright | `#e8c49a` | Highlights, selected state stroke |
| Text primary | `#f5f0eb` | Main labels (warm near-white) |
| Text secondary | `#a39787` | Sub-labels, descriptions |
| Text muted | `#6b5f53` | Annotations, fine print |

## Typography

```
Title / Section label:  Georgia, 'Times New Roman', serif
                        font-size: 21px (title), 14px (section labels)
                        font-weight: 700; fill: #f5f0eb / #c9a96e

Node name:              -apple-system, 'Helvetica Neue', Arial, 'PingFang SC', sans-serif
                        font-size: 13–14px, font-weight: 600, fill: <bucket color>

Sub-label / detail:     sans-serif, font-size: 10–11px, fill: #a39787 or #6b5f53

Arrow label / legend:   sans-serif, font-size: 10–11px, fill: #a39787

Code / path text:       'Cascadia Code', 'SF Mono', 'Courier New', monospace
                        font-size: 10–11px, fill: #a39787
```

Rule: Georgia serif ONLY for diagram titles and cluster/section labels (≥14px). All node names, arrow labels, and fine-print use sans-serif.

## Node Semantic Color Buckets

| Bucket | Border Color | Use For |
|--------|-------------|---------|
| Code / Logic | `#5a9e6f` (sage green) | functions, classes, modules, algorithms |
| Service / API | `#a78bfa` (soft violet) | services, endpoints, APIs, gateways |
| Data / Storage | `#38bdf8` (sky blue) | databases, tables, files, caches |
| Concept / Domain | `#f87171` (soft rose) | concepts, domains, entities, topics |
| Infra / Config | `#fbbf24` (amber yellow) | infrastructure, config, scripts, pipelines |
| Meta / Doc | `#94a3b8` (cool gray) | documents, schemas, resources, sources |

All nodes: `rx="6"`, `fill="#111111"`, `stroke-width="1.5"`, stroke = bucket color.

```xml
<!-- Code / Logic node example -->
<rect x="60" y="100" width="260" height="52" rx="6"
      fill="#111111" stroke="#5a9e6f" stroke-width="1.5"/>
<text x="72" y="122" font-family="-apple-system,'Helvetica Neue',Arial,sans-serif"
      font-size="13" font-weight="600" fill="#5a9e6f">MyComponent</text>
<text x="72" y="138" font-family="-apple-system,sans-serif"
      font-size="10" fill="#a39787">React component · state management</text>
```

## Arrow System

| Flow Type | Color | Stroke | Dash |
|-----------|-------|--------|------|
| Primary / structural | `#d4a574` gold | 2px solid | none |
| Data flow | `#6ee7b7` mint | 1.5px solid | none |
| Control / trigger | `#fdba74` amber-orange | 1.5px solid | none |
| Reference / semantic | `#a39787` warm muted | 1px dashed | `4,3` |
| Dependency | `#a78bfa` violet | 1px dashed | `6,3` |
| Feedback / loop | `#d4a574` gold | 1.5px curved | — |

```xml
<defs>
  <marker id="arr-gold" markerWidth="10" markerHeight="7"
          refX="9" refY="3.5" orient="auto">
    <polygon points="0 0,10 3.5,0 7" fill="#d4a574"/>
  </marker>
  <marker id="arr-orange" markerWidth="8" markerHeight="6"
          refX="7" refY="3" orient="auto">
    <polygon points="0 0,8 3,0 6" fill="#fdba74"/>
  </marker>
  <marker id="arr-blue" markerWidth="10" markerHeight="7"
          refX="9" refY="3.5" orient="auto">
    <polygon points="0 0,10 3.5,0 7" fill="#38bdf8"/>
  </marker>
  <marker id="arr-gray" markerWidth="8" markerHeight="6"
          refX="7" refY="3" orient="auto">
    <polygon points="0 0,8 3,0 6" fill="#94a3b8"/>
  </marker>
</defs>
```

Arrow labels: offset-first — 6–8px above horizontal arrows. Add `fill="#0a0a0a" opacity="0.9"` background rect only on collision.

## Container / Cluster Style

```xml
<rect x="40" y="80" width="880" height="140" rx="8"
      fill="none" stroke="#d4a574" stroke-width="0.5"
      stroke-dasharray="6,4" opacity="0.4"/>
<!-- Cluster label: Georgia serif, gold muted -->
<text x="52" y="98"
      font-family="Georgia,'Times New Roman',serif"
      font-size="11" font-weight="700"
      fill="#c9a96e" opacity="0.7">LAYER NAME</text>
```

## Background Treatment

No gradient needed — depth from contrast levels:
1. Canvas `#0a0a0a` — absolute black floor
2. Node surface `#111111` — first elevation
3. Panel/sub-header `#1a1a1a` — second elevation
4. Gold `#d4a574` — the only warmth; draws the eye to structure

Optional ambient glow around central cluster:

```xml
<defs>
  <radialGradient id="glow" cx="50%" cy="50%" r="30%">
    <stop offset="0%"   stop-color="#d4a574" stop-opacity="0.04"/>
    <stop offset="100%" stop-color="#d4a574" stop-opacity="0"/>
  </radialGradient>
</defs>
<rect width="960" height="600" fill="url(#glow)"/>
```

## Full `<style>` Block

```xml
<style>
  text { font-family: -apple-system,"Helvetica Neue",Arial,"PingFang SC",sans-serif; }
  .ttl { font-family: Georgia,"Times New Roman",serif;
         font-size: 21px; font-weight: 700; fill: #f5f0eb; }
  .lbl { font-family: Georgia,"Times New Roman",serif;
         font-size: 11px; font-weight: 700; fill: #c9a96e; opacity: 0.7; }
  .nm  { font-size: 13px; font-weight: 600; }    /* node name — fill set per bucket */
  .sm  { font-size: 10px; fill: #a39787; }        /* sub-label */
  .xs  { font-size:  9px; fill: #6b5f53; }        /* fine print */
  .al  { font-size: 10px; fill: #8c7e72; }        /* arrow label */
  .fn  { font-family: "Cascadia Code","SF Mono","Courier New",monospace;
         font-size: 10px; fill: #a39787; }        /* code / path text */
</style>
```

## ViewBox Recommendations

| Diagram | ViewBox |
|---------|---------|
| Standard architecture | `0 0 960 600` |
| Tall pipeline / flow | `0 0 960 820` |
| Wide multi-layer | `0 0 1200 600` |

## When to Choose Style 8

Architecture/pipeline docs where editorial gravitas matters: README hero images, conference slides, knowledge-base diagrams, premium product docs. Not recommended for UML class/ER diagrams or comparison tables.
