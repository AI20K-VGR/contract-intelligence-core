# Style 6: Official Warm

Warm, approachable, professional editorial style.

## Colors

```
Background:     #f8f6f3  (warm cream)

Node semantic fills:
  Input/Source:    #a8c5e6  (soft blue)
  Agent/Process:   #9dd4c7  (soft teal-green)
  Infrastructure:  #f4e4c1  (warm beige)
  Storage/State:   #e8e6e3  (light gray)

Box stroke:     #4a4a4a  (dark gray)
Box radius:     12px
Text primary:   #1a1a1a  (near black)
Text secondary: #6a6a6a  (medium gray)
Arrow color:    #5a5a5a  (consistent dark gray)
```

## Typography

```
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue',
             Arial, 'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif
font-size:   16px node labels, 14px descriptions, 13px arrow labels
font-weight: 600 for node labels, 400 for descriptions, 700 for titles
```

## Box Shapes

```xml
<!-- Agent node (teal-green) -->
<rect rx="12" ry="12" fill="#9dd4c7" stroke="#4a4a4a" stroke-width="2.5"/>

<!-- Input/Source node (soft blue) -->
<rect rx="12" ry="12" fill="#a8c5e6" stroke="#4a4a4a" stroke-width="2.5"/>

<!-- Infrastructure node (warm beige) -->
<rect rx="12" ry="12" fill="#f4e4c1" stroke="#4a4a4a" stroke-width="2.5"/>

<!-- Storage/State node (light gray) -->
<rect rx="12" ry="12" fill="#e8e6e3" stroke="#4a4a4a" stroke-width="2.5"/>
```

## Arrows

```xml
<defs>
  <marker id="arrow-warm" markerWidth="8" markerHeight="8"
          refX="7" refY="4" orient="auto">
    <polygon points="0 0, 8 4, 0 8" fill="#5a5a5a"/>
  </marker>
</defs>
<!-- Solid arrow for reads/primary -->
<line stroke="#5a5a5a" stroke-width="2" marker-end="url(#arrow-warm)"/>
<!-- Dashed arrow for writes -->
<line stroke="#5a5a5a" stroke-width="2" stroke-dasharray="5,3" marker-end="url(#arrow-warm)"/>
```

Arrow labels should be technical and specific: `query(text)`, `retrieve(top_k=5)`, `embed(768d)`.

## Node Content

Use 2–3 lines per node:
1. Component name (bold, 16px)
2. Technical detail or implementation (14px)
3. Key parameter or constraint (14px, optional)

## Layer Labels

For multi-layer architectures, add layer labels on the left side:

```xml
<text x="30" y="130" fill="#6a6a6a" font-size="14" font-weight="600">Input</text>
<text x="30" y="290" fill="#6a6a6a" font-size="14" font-weight="600">Processing</text>
<text x="30" y="490" fill="#6a6a6a" font-size="14" font-weight="600">Storage</text>
```

## Legend (when 2+ arrow types)

```xml
<rect x="720" y="520" width="220" height="68" rx="8" ry="8"
      fill="#ffffff" stroke="#4a4a4a" stroke-width="1.5"/>
<text x="735" y="540" fill="#1a1a1a" font-size="13" font-weight="600">Legend</text>
<line x1="735" y1="555" x2="765" y2="555" stroke="#5a5a5a" stroke-width="2"/>
<text x="775" y="560" fill="#6a6a6a" font-size="12">Read operation</text>
<line x1="735" y1="570" x2="765" y2="570" stroke="#5a5a5a" stroke-width="2" stroke-dasharray="5,3"/>
<text x="775" y="575" fill="#6a6a6a" font-size="12">Write operation</text>
```

## SVG Template

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 600"
     width="960" height="600">
  <style>
    text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                   'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei',
                   'Microsoft JhengHei', 'SimHei', sans-serif; }
  </style>
  <defs>
    <marker id="arrow-warm" markerWidth="8" markerHeight="8"
            refX="7" refY="4" orient="auto">
      <polygon points="0 0, 8 4, 0 8" fill="#5a5a5a"/>
    </marker>
    <filter id="shadow-soft">
      <feDropShadow dx="0" dy="2" stdDeviation="6" flood-color="#00000008"/>
    </filter>
  </defs>
  <rect width="960" height="600" fill="#f8f6f3"/>
  <!-- nodes, edges, legend -->
</svg>
```
