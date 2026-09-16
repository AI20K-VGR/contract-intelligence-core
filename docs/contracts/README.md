# Contracts

## `ai1.snapshot.v1`

[`ai1.snapshot.v1.schema.json`](ai1.snapshot.v1.schema.json) is the wire-shape contract from the Python OCR/layout worker to Spring. It rejects the legacy text-only OCR shape by requiring a snapshot identity, source digest, producer configuration and per-page render provenance.

JSON Schema cannot express every cross-field invariant. Spring's semantic validator must additionally verify:

- unique page, line, word, table and cell IDs within their declared scope;
- the source/render digest and document/dossier IDs match the task/run that submitted the artifact;
- `0 <= x0 < x1 <= 1` and `0 <= y0 < y1 <= 1` for every non-null CPS bbox;
- Unicode-code-point spans resolve to the exact raw line substring, and each word span belongs to its line;
- a measured word bbox has `native`, `detector` or `human` provenance; `line_only`, `derived` and `absent` never satisfy word-level evidence;
- table cells resolve their required line IDs; all citations resolve the pinned snapshot and render;
- source/render objects are readable only through the authorized internal URI scheme and their SHA-256 values match.

The worker result envelope and public API are deliberately separate: see [DOC-04](../DOC-04-architecture.md) and [DOC-05](../DOC-05-api-spec.yaml).

## Optimization Control Plane v1

[`optimization-control-plane.v1.schema.json`](optimization-control-plane.v1.schema.json) defines the wire shapes for immutable config bundles, optimizer-proposed typed patches, and pre-registered evaluation plans. The server additionally verifies patch paths against the stored allowed-knob set, canonicalizes the resulting bundle before digesting it, and enforces all lifecycle/approval/RBAC checks. A valid JSON document is never authority to activate a config or call an external provider.
