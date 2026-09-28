# Output Formats

## 8. Output Formats

Reference: `output/reports/`, `connectors/`

### Mandatory File Export (CRITICAL)

**Every `/report`, `/brief`, and `/case` command MUST auto-save two files to disk at the end of delivery:**

1. **Markdown report** — saved as `OSINT-REPORT-[CASE-ID]-[YYYY-MM-DD].md`
2. **Word document** — saved as `OSINT-REPORT-[CASE-ID]-[YYYY-MM-DD].docx`

**Save location:** Current working directory, or `./osint-reports/` subdirectory if it exists.

**DOCX generation (Rich format with charts & diagrams):**

**Step 1 — Build the DOCX-ready JSON file.** The Python generator expects a SPECIFIC flat format (NOT the engine case-schema.json). You MUST construct the JSON matching this exact structure before calling the script. Reference: `scripts/sample-cti-report-data.json`.

```json
{
  "case": {
    "id": "CTI-2026-001",          // string, case identifier
    "label": "Case Title",         // string, human-readable name
    "classification": "OPEN SOURCE", // string
    "analyst": "AI-Assisted CTI",  // string
    "date": "2026-04-08",          // ISO date
    "subject": "target.com",       // string, primary subject
    "status": "active",            // string
    "exposure_score": 72           // integer 0-100 (optional, enables risk gauge)
  },
  "executive_summary": "Full paragraph summarizing investigation findings...",
  "subjects": [
    {
      "id": "SUB-001",            // string ID (not UUID)
      "label": "target.com",      // human-readable name — REQUIRED for display
      "type": "domain",           // lowercase: domain, person, ip, organization, email, username
      "confidence": 95,           // INTEGER 0-100 (not string like "VERIFIED")
      "verified": true,           // boolean
      "aliases": ["alias1"],      // string array
      "first_seen": "2025-01-15", // ISO date string
      "notes": "Primary domain"   // string
    }
  ],
  "findings": [
    {
      "id": "FND-001",            // string ID
      "subject_id": "SUB-001",    // links to subject
      "type": "infrastructure",   // credential, infrastructure, identity, exposure, behavioral, legal
      "weight": "HIGH",           // CRITICAL, HIGH, MEDIUM, LOW, INFO — drives severity colors
      "description": "Full description of the finding...",
      "source_url": "https://...",
      "collected_at": "2026-04-08T10:00:00Z",
      "confidence": 88,           // INTEGER 0-100 (not string)
      "tags": ["tag1", "tag2"]
    }
  ],
  "connections": [
    {
      "id": "CON-001",
      "from_id": "SUB-001",       // subject ID
      "to_id": "SUB-002",         // subject ID
      "relationship": "owns",     // string describing relationship
      "strength": "confirmed"     // confirmed, probable, possible
    }
  ],
  "timeline": [
    {"date": "2025-01-15", "event": "Domain registered"}
  ],
  "sources": [
    {"name": "Source Name", "url": "https://...", "date": "2026-04-08"}
  ],
  "intelligence_gaps": [
    "Gap description string"
  ],
  "recommendations": [
    "Action item string"
  ],
  "visitor_stats": {              // optional — enables visitor intelligence charts
    "domain": "target.com",
    "monthly_visits": 150000,
    "traffic_sources": {"direct": 42, "search": 28, "referral": 15, "social": 10, "paid": 5},
    "top_countries": [{"country": "Vietnam", "share": 60}, {"country": "US", "share": 20}]
  },
  "caveats": ["Caveat string"]   // optional — overrides default methodology notes
}
```

**CRITICAL FORMAT RULES:**
- `confidence` on subjects and findings MUST be an **integer** (e.g., `85`), NOT a string (e.g., `"VERIFIED"`)
- `findings` MUST be a **flat top-level array**, NOT nested inside subjects
- `label` is REQUIRED on each subject (this is what displays in the report — not `value` or `display_name`)
- `weight` on findings drives severity coloring — use CRITICAL/HIGH/MEDIUM/LOW/INFO
- `recommendations` must be an array of **strings** (not objects with `priority`/`action` keys)
- All fields shown above should be **populated with actual data** — empty strings or "N/A" defeat the purpose
- Populate `executive_summary` with a full paragraph — most-read section of the report

**Step 2 — Save the JSON and run the generator:**
```bash
# Primary: HYBRID generator — full narrative from MD + charts/diagrams from JSON
# This produces a complete DOCX with ZERO content loss from the MD report
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cti-expert/scripts/generate-cti-docx-hybrid.py \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].md" \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].json" \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].docx"

# Fallback 1: JSON-only generator (charts + structured data, less narrative)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cti-expert/scripts/generate-cti-docx.py \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].json" \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].docx"

# Fallback 2: MD-only mode (styled narrative, no charts — JSON optional)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cti-expert/scripts/generate-cti-docx-hybrid.py \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].md" \
  "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].docx"

# Fallback 3: pandoc (basic text conversion, no styling or charts)
pandoc "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].md" \
  -o "CTI-REPORT-[CASE-ID]-[YYYY-MM-DD].docx" \
  --from markdown --to docx --standalone
```

**How the hybrid generator works:**
1. **Phase 1:** pandoc converts the MD file to a base DOCX (preserving ALL narrative content — tables, lists, formatting)
2. **Phase 2:** python-docx post-processes to add CTI professional styling, prepend cover page + TOC, and inject charts/diagrams from JSON at matching section headings

**The MD file is the primary content source** — full narrative (person profiles, infrastructure tables, wallet addresses, corporate structure, legal history, etc.). JSON provides structured data for visual elements (charts, diagrams, risk gauge). Together: complete report, zero content loss.

**Rich hybrid DOCX includes:** Cover page titled "CTI REPORT", table of contents, **all narrative content from MD** (every paragraph, table, list, code block), pie chart (finding types), bar chart (severity), risk gauge (exposure score), timeline chart, entity relationship diagram, network topology diagram, traffic/geo charts, CTI-themed styling (navy headings, styled tables), header/footer
with classification and page numbers.

**After saving, confirm all files to the user:**
```
📄 Report saved:
   → CTI-REPORT-CASE001-2026-03-30.md
   → CTI-REPORT-CASE001-2026-03-30.json
   → CTI-REPORT-CASE001-2026-03-30.docx  (rich format with charts & diagrams)
```

### Report Formats

| Format | Command | Audience |
|--------|---------|---------|
| Technical INTSUM | `/report` | Analysts, security teams |
| Executive Brief | `/report brief` | Decision-makers, management |
| Plain-Language Summary | `/brief` | Non-technical stakeholders |
| Legal Evidence Format | `/report legal` | Attorneys, compliance teams |
| Journalist Format | `/report journalist` | Reporters, media |
| JSON Export | `/report json` | Downstream tools, pipelines |
| CSV Export | `/report csv` | Spreadsheets, databases |

All formats above auto-save as .md + .docx unless the format is inherently machine-only (JSON, CSV — those save as their native format only).

### Visual Outputs

| Type | Command | Format |
|------|---------|--------|
| Subject relationship map | `/render entities` | **ASCII** (default) — `--mermaid` for Mermaid |
| Chronological timeline | `/render timeline` | **ASCII** Gantt |
| Exposure heatmap | `/render risk` | **ASCII** |
| Network topology | `/render network` | **ASCII** |

**All visual outputs use ASCII box-drawing by default.** Mermaid only on explicit `--mermaid` flag.

### Connectors

| Tool | File | What It Exports |
|------|------|----------------|
| Maltego | `connectors/maltego-export.md` | GraphML entity graph |
| Obsidian | `connectors/obsidian-setup.md` | Linked markdown notes |
| Notion | `connectors/notion-schema.md` | Structured database |

---

