# Security scan: AI2 graph UI P5

Date: 2026-10-11
Scope: AI2 graph read projection, Backend graph and trace routes, frontend citation fallback, and frontend dependency tree touched/used by P5.
Method: changed-tree credential sweep; manual STRIDE/OWASP code-path review; `npm audit` production and full-tree checks. This is a source review, not a penetration test or runtime infrastructure audit.

## Findings (initial scan; superseded where noted below)

- **High, fixed — production dependency denial of service.** `source-map-js` 1.2.1 was pulled by `@tailwindcss/node` and Vite/PostCSS and matched GHSA-68fv-2mgg-jv7q (`>=1.0.0 <1.2.2`). Updated the existing lockfile resolution to 1.2.2 with `npm update source-map-js`; no direct dependency range changed. `npm audit --omit=dev --audit-level=high` now reports zero vulnerabilities. Frontend tests (139/139) and production build pass after the update.
- **Critical/moderate, open — development-only test dependencies.** Full `npm audit --audit-level=high` reports two critical `tinypool` advisories and one moderate Vitest mocker advisory through Vitest 3.2.7. npm only offers Vitest 5.0.3, a major upgrade. These packages are development dependencies and are not included in the production audit. Kept the P5 runtime dependency scope stable; schedule a Vitest major upgrade with its own compatibility/test pass.
- **Unverified — Python dependency audit.** The Backend virtual environment does not have `pip-audit` installed (`No module named pip_audit`), so no Python CVE conclusion is made.

## Trust-boundary review

- Backend graph and trace read endpoints require `CITATION_READ` authorization on the dossier before issuing the internal AI2 read, bind the request to authenticated tenant/dossier/actor identity, and use a scoped service envelope. The AI2 graph route validates the envelope scope and tenant/dossier/job/snapshot identity before reading persisted rows.
- Graph projection exposes node and source-document identities plus opaque citation references; it does not expose citation text or spans. Frontend response parsing rejects unsupported fields and malformed/missing document provenance.
- Legacy OCR citation fallback fails closed except for an opaque `cite:` handle, an explicit API 404, and an exact match between endpoint source document and selected document. 403, 5xx, network failures, non-opaque IDs, and missing/mismatched identity stay errors; the fallback does not broaden authorization to the PDF/document QUERY path.
- Graph cursors are kind-prefixed and length-limited; page limits and bounded internal response bytes are enforced. No user-controlled SQL fragments or HTML rendering of contract text were found in the reviewed graph path.

## Limits

The mechanical credential-pattern scan covers only the changed working tree and excludes tests, docs, lockfiles, ignored/binary files, and content beyond its configured file-size cap. This review did not inspect unchanged history or infrastructure, did not exercise authorization against a live deployment, and does not establish browser/runtime security. No credentials are included in this report.

## Verdict

No unresolved high/critical finding was found in the production dependency tree or reviewed P5 graph/citation code paths after the lockfile update. Follow-up scans on 2026-10-12 found zero known npm vulnerabilities and no known vulnerabilities in the exported AI-service and Backend runtime Python dependencies. These are dependency scans plus source review, not a penetration test, deployment audit, or proof of OCR-to-graph generation. The earlier findings above are retained as historical context and marked fixed/verified. This report is scoped evidence, not a blanket security certification.


## Follow-up ? 2026-10-12

- `npm audit --audit-level=high`: zero vulnerabilities after the Vitest 5.0.3 upgrade. CI and local engine declaration target Node 24.
- `pip-audit` against exported runtime dependency sets for AI service and Backend: no known vulnerabilities.
- Source review/fixes also covered terminal graph failure propagation, malformed `job_status` rejection, trace fallback preserving known job state, and responsive mobile dialog teardown at desktop breakpoint.
- Remaining scope limit: synthetic seeded browser/API data validates presentation, authorization, and citation retrieval only; it does not show graph generation from OCR or assess deployed infrastructure.
