# docs

Product and technical documents, one file per deliverable (Markdown, OpenAPI YAML for the API spec).
Images and diagrams go in `assets/` (the only folder in the repo where image files are allowed).

| file | document | due | reviewer |
|---|---|---|---|
| `DOC-01-product-vision.md` | Product Vision | Sprint 1 (20/09) | mentor |
| `DOC-02-brd.md` | BRD | Sprint 1 (20/09) | mentor |
| `DOC-03-prd.md` | PRD | Sprint 1 (20/09) | mentor |
| `DOC-04-architecture.md` | Architecture | Sprint 2 (04/10) | mentor |
| `DOC-05-api-spec.yaml` | API Spec | Sprint 2 (04/10) | mentor |
| `DOC-06-eval-report.md` | Evaluation Report | Sprint 3 (18/10) | mentor |

`DOC-04-architecture.md` and `DOC-05-api-spec.yaml` are the earlier sprint deliverables; the
current living architecture doc is **[architecture.md](architecture.md)** (see root README),
kept in sync with the actual FastAPI/Postgres implementation. The `DOC-*` files stay as-is for
mentor traceability — do not delete them.

Changes to a document go through a PR like code (2 approvals). The sprint tracker on OneDrive
holds the status of each document.
