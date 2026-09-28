# Layout tips — hs:drawio

Spacing, routing corridors, and placement rules for clean diagrams.

## Spacing — scale with complexity

| Diagram complexity | Nodes | Horizontal gap | Vertical gap |
|---|---|---|---|
| Simple | ≤5 | 200px | 150px |
| Medium | 6–10 | 280px | 200px |
| Complex | >10 | 350px | 250px |

Larger diagrams need wider gaps — edges need room to route without crossing shapes.

## Routing corridors

Between shape rows/columns, leave an extra ~80px empty corridor where edges can route without crossing shapes. Never place a shape in a gap that edges need to traverse.

## Hub-centering

Place Kafka/bus/EventBridge nodes in the **center of the service row**, not below. Services on either side can reach it with short horizontal arrows (`exitX=1` left side, `exitX=0` right side), eliminating all line crossings.

## Straight connections

To force straight vertical connections, pin entry/exit points explicitly:

```
exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0
```

Always center-align a child node under its parent (same center x) to avoid diagonal routing.

## Edge-shape overlap avoidance

- Trace each edge path mentally before finalizing — if it crosses an unrelated shape, move the shape or add waypoints.
- Tree/hierarchical: assign nodes to layers, connect only between adjacent layers.
- Star/hub: place hub center, satellites around it — edges stay short and radial.
- Long detours: route edges along the outer corridor, not through the middle.

## General rules

- Horizontal connections (`exitX=1` or `exitX=0`) never cross vertical nodes in the same row — use them for peer-to-peer and publish connections.
- Plan a grid before assigning x/y — sketch node positions first.
- Place connected things near each other: shared resources in a band next to consumers, not in a far-away row. `validate.py` flags long connectors and edge crossings — fix placement, not routing.
