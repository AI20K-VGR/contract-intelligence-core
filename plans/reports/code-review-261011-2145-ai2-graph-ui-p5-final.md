# Final P5 Code Review — AI2 Graph UI

## Code Review Summary

### Scope

- Files: 22 files covering the AI2 graph projection/read route, Backend adapter and ACL-protected routes, frontend graph client/views/page, tests, versioned graph/trace schemas, and the frontend lockfile.
- LOC: 7,052 lines across the complete source/schema files; the shared Backend router/adapter files contain unrelated existing code, and the generated lockfile is excluded, so this is file-surface LOC rather than changed LOC.
- Focus: final P5 review of AI2 → Backend → Frontend graph read contract, citation provenance/fallback, cross-document node identity, UI state and accessibility hooks.
- Scout findings: equal node IDs can occur in different dossier documents; citation source document provenance can be absent; an error fallback can mask authorization/service failures or open a clause from the wrong document. The current code addresses these cases as described below.

### Overall Assessment

**PASS for the scoped code review.** No confirmed correctness, security, contract, or regression defect remains in the reviewed P5 surfaces. This verdict covers code review only; the plan's manual browser acceptance and full-worktree gates remain separate and unresolved.

### Critical Issues

None found.

### High Priority

None found.

### Medium Priority

No P5 runtime-code defect found. Separate toolchain risk: full `npm audit` reports one moderate advisory in `@vitest/mocker@3.2.7` and two critical advisories in `tinypool@1.1.1`, both in the dev-only Vitest 3.2.7 test dependency chain. `npm audit --omit=dev` reports zero vulnerabilities. npm's suggested automatic fix requires the breaking Vitest 5 upgrade; handle that as a separate dependency update and validate CI/test behavior before adopting it.

### Low Priority

None found.

### Edge Cases Found by Scout

- `ContractGraphCanvas.tsx:333-360` keys known nodes by document and node identity. Endpoints without a document ID receive a per-edge/per-side identity, preventing same-named nodes from separate unknown documents from being merged. Regression coverage asserts duplicate IDs remain separate.
- `RelationInspector.tsx:57-75` passes endpoint document IDs with citation actions. `DossierStructurePage.tsx:498-518` allows the legacy OCR fallback only for a `cite:` handle, explicit HTTP 404, matching selected/source document IDs, and a locally loaded clause/citation. 403, 5xx, transport errors, missing provenance, or cross-document IDs remain visible errors.
- Async citation loads use a request version guard; stale success/error results cannot replace the latest selection.
- AI2's internal read route authenticates a signed service envelope and scopes the job query to tenant, dossier, job, and snapshot. Backend routes require `CITATION_READ`, recheck ACL and snapshot after the AI2 await, and bind cursors to tenant/dossier/job/digest/kind. Frontend parsing rejects malformed response shapes and provenance fields.

### Positive Observations

- The graph DTO projects opaque citation refs and endpoint document IDs, not citation text or spans.
- UI graph/trace reads stay behind the default-off flag and graph view; the accessible paginated relation list remains the full traversal path.
- Canvas and list selection share edge IDs, and the canvas explicitly identifies its page as bounded.
- The final lock-only patch resolves `source-map-js` 1.2.2; `package.json` is unchanged and the lock diff contains only this transitive resolution update. `npm ci --ignore-scripts --dry-run --no-audit --no-fund` completed successfully.

### Recommended Actions

1. Keep P5 phase status pending until the manual 320 CSS px, keyboard/focus, and live citation checks have receipts.
2. Refresh `verification-P5.json` and `p5-implementation.md`: they still record 22 focused and 137 full-suite tests; the latest focused run is 24 tests, and the lead reports the latest full suite as 139 tests across 36 files.
3. Complete the separate whole-worktree architecture/security ceremony before any ship decision; the current branch also contains structural migrations outside this scoped review.

### Metrics

- Type/Lint Coverage: `npm run build` passed (`tsc -b` + Vite); `npm run lint` passed with 0 errors and 13 warnings.
- Test Coverage: focused frontend rerun passed, 24 tests across 3 files. The lead reports 139/139 tests across 36 files on the latest full frontend run after the null-provenance canvas fix; AI2 projection reported 9 passing tests; Backend graph adapter reported 13 passing tests.
- Linting Issues: 0 errors; 13 warnings.
- Build: passed; Vite reports the existing >500 kB chunk-size warning.
- Dependency audit: production (`npm audit --omit=dev`) clean; full audit reports 3 dev-only findings (1 moderate, 2 critical) in the Vitest/Tinypool chain.
- Fan-in (data only): no `code.fan_in` envelope was provided.

### Unresolved Questions

- Manual 320 CSS px overflow, actual browser keyboard/focus behavior, visual readability, and live citation navigation were not exercised because the in-app browser and running Backend/Keycloak were unavailable. Do not infer those results from server-rendered component tests.
- Dev-only Vitest/Tinypool advisories remain; the P5 lock patch fixes the production dependency audit but does not remediate the test-runner chain.
- The worktree-wide `hs-run review next` risk/architecture state includes API changes and migrations outside this P5 assignment. This scoped PASS is not evidence that those separate gates passed.
