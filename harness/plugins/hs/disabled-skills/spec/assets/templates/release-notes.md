<!--
NOT SHIPPED as a live flow: `--summary --audience release-notes` is not a
flow hs:spec exposes (see workflow-validate.md's caveat), and the audit-trail
assembler this audience needs (`assemble_audit_trail.py`) does not exist on
disk — the same absent script behind the retired `--viz audit` view. This
template IS real and generatable (`generate_templates.py --type
release_notes --write` works), but no shipped flow assembles the values and
calls it for the PO today.

TEMPLATE: release-notes.md — `--summary --audience release-notes` output, as
designed. "What changed since the last approved snapshot", pulled from the
audit trail. Same source-of-truth + render path as the exec one-pager;
different audience. Bilingual headers.
-->
---
id: RELEASE-NOTES
type: release_notes
status: {{status}}
lang: {{lang}}
owner: {{owner}}
version: {{version}}
created: {{created}}
updated: {{updated}}
generated_at: {{generated_at}}
---

# Release Notes — {{name}} | Ghi chú phát hành

## Since Last Approved | Kể từ lần duyệt gần nhất

{{changes_since_approved}}

## Open Risks | Rủi ro mở

{{top_risks}}
