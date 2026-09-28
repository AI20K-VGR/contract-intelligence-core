# Phase 5 release checklist

Generated after the local stack smoke run. No secret or access token is stored here.

| Gate | Result | Evidence |
|---|---|---|
| Frontend contract/build/tests | PASS | `npm test`: 10 passed; `npm run build`: exit 0 |
| Frontend changed-file formatting | PASS | Prettier check passed for changed frontend files |
| Frontend lint | PASS with warnings | 0 errors; 6 pre-existing warnings |
| AI2 offline suite | PASS | `687 passed, 6 deselected` with `-m "not live"` |
| Backend review/extraction/conflict | PASS | review/approval 21 passed; extraction/conflict 19 passed |
| Docker backend health | PASS | `GET http://127.0.0.1:8000/health` returned `status=ok` |
| Docker AI2 health | PASS | `GET http://127.0.0.1:8002/health` returned `status=ok`, `llm=ready` |
| Frontend root smoke | PASS | `http://127.0.0.1:5173/` returned HTTP 200 |
| Authenticated dossier detail smoke | PASS | PKCE login succeeded; `GET /api/v1/dossiers/dos_01M38T3PD2Z45CJXGS6FQGKSWX` returned HTTP 200 |
| Docker service state | PASS/limited | backend, AI2, backend-db and keycloak-db healthy; workers/Kafka/Keycloak/MinIO running without compose health status |
| Authenticated upload → OCR → AI1 → AI2 → review → approve | NOT_RUN | no new upload/review mutation was run; lock/approve requires explicit dossier confirmation |
| Live provider replay | NOT_RUN | offline gate passed; live credential-dependent replay was intentionally not claimed |

## Safe-state guarantees

- Search and structured analysis preserve `NEEDS_REVIEW`/`PARTIAL`/`UNRESOLVED` when citation location is incomplete.
- Review actions send `base_version`; HTTP 409 is surfaced as a conflict and reloads the queue.
- CSV export contains dossier/query/answer/review state/citation metadata only; it never includes API keys or bearer tokens.
- Dedicated relation-graph/risk contracts remain outside the Backend API exposed to the UI; no mock relation/risk result is emitted.
