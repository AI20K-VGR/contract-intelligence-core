# Excalidraw JSON schema

## Element types

| Type | Used for |
|---|---|
| `rectangle` | Process, action, component |
| `ellipse` | Entry/exit point, external system, actor |
| `diamond` | Decision, conditional |
| `arrow` | Connection between shapes |
| `text` | Label (standalone or inside a shape) |
| `line` | Structural line (not an arrow) |
| `frame` | Grouping container |

## Common properties

| Property | Type | Description |
|---|---|---|
| `id` | string | Unique identifier — use descriptive names (e.g. `"api_rect"`) |
| `type` | string | Element type |
| `x`, `y` | number | Position in pixels |
| `width`, `height` | number | Size in pixels |
| `strokeColor` | string | Border color (hex) |
| `backgroundColor` | string | Fill color (hex or `"transparent"`) |
| `fillStyle` | string | `"solid"`, `"hachure"`, `"cross-hatch"` |
| `strokeWidth` | number | 1, 2, or 4 |
| `strokeStyle` | string | `"solid"`, `"dashed"`, `"dotted"` |
| `roughness` | number | 0 (smooth), 1 (default), 2 (rough) |
| `opacity` | number | 0-100 (always use 100) |
| `seed` | number | Random seed for roughness -- namespace by section |
| `angle` | number | Rotation in radians (usually 0) |
| `isDeleted` | boolean | Always `false` |
| `groupIds` | array | `[]` if not grouped |
| `locked` | boolean | Always `false` |
| `link` | null | Always `null` |

## Text-specific

| Property | Description |
|---|---|
| `text` | Displayed text |
| `originalText` | Same as `text` |
| `fontSize` | Pixels (16 for labels, 20-24 for titles) |
| `fontFamily` | `3` for monospace -- **always** |
| `textAlign` | `"left"`, `"center"`, `"right"` |
| `verticalAlign` | `"top"`, `"middle"`, `"bottom"` |
| `containerId` | ID of the parent shape (`null` if free-floating) |
| `lineHeight` | `1.25` (default) |

## Arrow-specific

| Property | Description |
|---|---|
| `points` | Array of `[x, y]` coordinates -- 2 points for straight, 3+ for curve |
| `startBinding` | Connection to the start shape |
| `endBinding` | Connection to the end shape |
| `startArrowhead` | `null`, `"arrow"`, `"bar"`, `"dot"`, `"triangle"` |
| `endArrowhead` | `null`, `"arrow"`, `"bar"`, `"dot"`, `"triangle"` |

## Binding format

```json
{
  "elementId": "shapeId",
  "focus": 0,
  "gap": 2
}
```

`focus`: -1 to 1 (0 = center). `gap`: pixel distance from the edge.

## Rectangle roundness

```json
"roundness": { "type": 3 }
```

## BoundElements (shape to text link)

The shape must declare its text in `boundElements`:
```json
"boundElements": [{"id": "text_id", "type": "text"}]
```

The text must declare `"containerId": "shape_id"`.

## File wrapper

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [...],
  "appState": {
    "viewBackgroundColor": "#ffffff",
    "gridSize": 20
  },
  "files": {}
}
```

## Seed namespacing (avoid collisions)

| Section | Seed range |
|---|---|
| Section 1 | 100000-199999 |
| Section 2 | 200000-299999 |
| Section 3 | 300000-399999 |
| Section N | N x 100000 to (N+1) x 100000 - 1 |

## Common mistakes

| Error | Fix |
|---|---|
| Text clipped | Increase `width`/`height` of the container |
| Arrow not bound | Check that `elementId` matches the correct `id` |
| Overlap | Increase gap: labeled arrows 150-200px, unlabeled 100-120px |
| Text not centered | Set `containerId` correctly + `textAlign: "center"` + `verticalAlign: "middle"` |
| Duplicate seed | Namespace by section |
