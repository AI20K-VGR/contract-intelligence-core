# Design methodology (detailed guide)

## Research mandate (technical diagrams)

**Before drawing any technical diagram, research the real spec.**

If the diagram depicts a protocol, API, or framework:
1. Look up the actual JSON/data format
2. Find the real event names, method names, API endpoints
3. Understand how the parts actually connect
4. Use real terminology, not generic placeholders

Bad: "Protocol" -> "Frontend"
Good: "AG-UI streams events (RUN_STARTED, STATE_DELTA)" -> "renderer handles via createA2UIMessageRenderer()"

---

## Evidence artifacts

Concrete examples prove accuracy and help the viewer learn something.

| Artifact type | When | How to render |
|---|---|---|
| Code snippet | API, integration | Dark rect (`#1e293b`) + syntax-colored text |
| Data/JSON example | Schema, payload | Dark rect (`#1e293b`) + green text (`#22c55e`) |
| Event sequence | Protocol, workflow | Timeline pattern (line + dots + labels) |
| UI mockup | Show real output | Nested rectangles simulating real UI |
| Real input content | What goes INTO the system | Rectangle with sample content |
| API/method name | Real function call | Real name from docs |

**Principle**: Show what things actually look like, not just what they are called.

---

## Multi-zoom architecture

A comprehensive diagram works at 3 zoom levels simultaneously:

### Level 1: Summary flow
Overview of the entire pipeline; usually top or bottom.
Example: `Input -> Processing -> Output`

### Level 2: Section boundaries
Labeled zones group related components. Creates visual "rooms".
Example: Group by responsibility (Backend/Frontend), phase (Setup/Execution/Cleanup)

### Level 3: Detail inside sections
Evidence artifacts, code snippets, concrete examples inside each section.
Example: Inside the "Backend" section, show the actual API response format.

**Comprehensive diagram: include all 3 levels.**

---

## Large diagram strategy (section-by-section)

**Large diagram: build JSON one section at a time** — output token limit blocks a full-file single pass.

### Phase 1: Build each section
1. Create the base file with JSON wrapper + first section
2. Add one section per edit — think carefully about layout and connections
3. Use descriptive IDs (e.g. `"trigger_rect"`, `"arrow_fan_left"`)
4. Namespace seeds by section (section 1: 100xxx, section 2: 200xxx)
5. Update cross-section bindings as sections are added

### Phase 2: Overall review
- Cross-section arrows bound correctly on both ends?
- Overall spacing balanced?
- Every ID references an element that actually exists?

### Phase 3: Render & validate
Run the render-view-fix loop.

### Section boundaries
Plan around natural visual groups:
- Section 1: Entry point / trigger
- Section 2: First decision/routing
- Section 3: Main content (hero section — largest)
- Sections 4-N: Remaining phases, output

### What not to do
- Do not generate the full diagram in a single response
- Do not write a Python generator script (indirection makes debugging harder)

---

## Container vs. free-floating text

| Use container when... | Use free-floating text when... |
|---|---|
| Focal point of a section | Label or description |
| Visual grouping needed | Supporting detail or metadata |
| Arrow connects into it | Describing something nearby |
| Shape carries meaning (decision diamond) | Section title, annotation |
| Represents a clear "thing" | Typography alone creates hierarchy |

**Typography is hierarchy**: a 28px title needs no rectangle.

---

## Layout principles

### Hierarchy through scale
- **Hero**: 300x150 — visual anchor
- **Primary**: 180x90
- **Secondary**: 120x60
- **Small**: 60x40

### Whitespace = importance
The most important element has 200px+ of space around it.

### Flow direction
Left to right or top to bottom for sequences; radial for hub-and-spoke.

### Relationship requires connection
Position alone ≠ relationship — every relationship needs an arrow.

---

## Lines as structure

Use line (`type: "line"`, not arrow) as the primary structural element:
- **Timeline**: Line + small dot (10-20px ellipse) + free-floating label
- **Tree structure**: Vertical trunk + horizontal branch + text label (no box)
- **Divider**: Thin dashed line to separate sections
- **Flow spine**: Central line that other elements attach to

Line + free-floating text > box + text inside.
