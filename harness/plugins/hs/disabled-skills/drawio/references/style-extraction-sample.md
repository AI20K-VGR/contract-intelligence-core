## Sample diagram (for approval render)

After extracting a candidate preset, render this seven-node sample using the candidate's palette/shapes/fonts/edges. Each role appears exactly once; six edges, one dashed, exercise `edges.arrow`, `edges.style`, and `edges.dashedFor`.

**Layout (TB):**
- Row 1 (y=40): `gateway` centered at x=340
- Row 2 (y=180): `security` (x=80), `service` (x=340), `queue` (x=600)
- Row 3 (y=340): `database` (x=80), `external` (x=340), `error` (x=600)

**Template — substitute `{{...}}` placeholders from the candidate preset.**

The vertex style for role `R` is built as:
`<shapes[R]>;whiteSpace=wrap;html=1;fillColor=<palette[roles[R]].fillColor>;strokeColor=<palette[roles[R]].strokeColor>;fontFamily=<font.fontFamily>;fontSize=<font.fontSize>`
- If `extras.sketch=true`, append `;sketch=1` to every vertex style AND every edge style.
- If `extras.globalStrokeWidth !== 1` (i.e., any value other than the drawio default of 1, including `0.5`), append `;strokeWidth=<n>` to every vertex style AND every edge style.

The edge style is built as:
`<edges.style>;<edges.arrow>`
- Per-edge routing keys (`exitX/entryX/...`) are added as literals below.
- Edge 15 exercises `edges.dashedFor`:
  - If `edges.dashedFor` is **non-empty**, use its first entry as the edge's `value` (label) AND append `;dashed=1` to the edge style.
  - If `edges.dashedFor` is empty (`[]`), use the label `cross-call` and do NOT append `;dashed=1` — the preset has no dashed convention, so the sample must not fake one.

**Placeholder expansion (applied when filling the XML):**
- `{{VSTYLE:<role>}}` expands to the vertex-style formula above with `R = <role>`. Write the result as a literal string; do not URL-encode.
- `{{ESTYLE}}` expands to the edge-style formula above.
- `{{EDGE15_LABEL}}` and `{{EDGE15_DASH}}` follow the Edge-15 rule above.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio" version="26.0.0">
  <diagram name="Preset Sample">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <!-- Row 1: gateway -->
        <mxCell id="2" value="Gateway" style="{{VSTYLE:gateway}}" vertex="1" parent="1">
          <mxGeometry x="340" y="40" width="160" height="60" as="geometry" />
        </mxCell>

        <!-- Row 2: security | service | queue -->
        <mxCell id="3" value="Auth" style="{{VSTYLE:security}}" vertex="1" parent="1">
          <mxGeometry x="80" y="180" width="160" height="60" as="geometry" />
        </mxCell>
        <mxCell id="4" value="Service" style="{{VSTYLE:service}}" vertex="1" parent="1">
          <mxGeometry x="340" y="180" width="160" height="60" as="geometry" />
        </mxCell>
        <mxCell id="5" value="Queue" style="{{VSTYLE:queue}}" vertex="1" parent="1">
          <mxGeometry x="600" y="180" width="160" height="60" as="geometry" />
        </mxCell>

        <!-- Row 3: database | external | error -->
        <mxCell id="6" value="Database" style="{{VSTYLE:database}}" vertex="1" parent="1">
          <mxGeometry x="80" y="340" width="160" height="70" as="geometry" />
        </mxCell>
        <mxCell id="7" value="External API" style="{{VSTYLE:external}}" vertex="1" parent="1">
          <mxGeometry x="340" y="340" width="160" height="60" as="geometry" />
        </mxCell>
        <mxCell id="8" value="Error Sink" style="{{VSTYLE:error}}" vertex="1" parent="1">
          <mxGeometry x="600" y="340" width="160" height="60" as="geometry" />
        </mxCell>

        <!-- Edges -->
        <mxCell id="10" value="" style="{{ESTYLE}};exitX=0.25;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="2" target="3">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="11" value="" style="{{ESTYLE}};exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="2" target="4">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="12" value="" style="{{ESTYLE}};exitX=0.75;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="2" target="5">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="13" value="" style="{{ESTYLE}};exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="4" target="7">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="14" value="" style="{{ESTYLE}};exitX=0;exitY=0.5;exitDx=0;exitDy=0;entryX=1;entryY=0.5;entryDx=0;entryDy=0" edge="1" parent="1" source="4" target="6">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="15" value="{{EDGE15_LABEL}}" style="{{ESTYLE}}{{EDGE15_DASH}};exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0" edge="1" parent="1" source="4" target="8">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

### Rendering the sample

1. Write the filled XML to `/tmp/drawio-preset-<name>.drawio`.
2. Run the same `drawio -x -f png -e -s 2 -o <preset-name>-sample.png <tmp>.drawio` command the main workflow uses (substitute the binary name you resolved in SKILL.md Step 1 if it isn't `drawio`).
3. Repair the IEND chunk: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/repair_png.py <preset-name>-sample.png` — the `-e` flag truncates the PNG the same way the main workflow's step 7 does, so the sample needs the same fix to be readable.
4. Save the PNG as `./preset-<name>-sample.png` (the user's working directory).
5. Show the user: preset summary table + PNG path + provenance/confidence line.

### Approval loop

- "save" / "looks good" → write candidate to `~/.drawio-skill/styles/<name>.json`; delete tempfile and sample PNG.
- "change <field> to <value>" → edit the in-memory candidate; re-render; re-ask.
- "cancel" → delete tempfile and sample PNG; no save.

### If sample render fails (draw.io CLI missing / export error)

Still show the summary table and the provenance line. Note: *"Could not render sample PNG (CLI unavailable). Save anyway on your OK."* Do not block.
