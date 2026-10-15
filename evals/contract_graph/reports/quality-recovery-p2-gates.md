# Quality recovery P2 — scoring and readiness gates

## Result

P2 implementation and offline verification pass. This is a code/test result only; no provider requests or real corpus evaluation were performed, and it does not establish product quality PASS.

The additive quality protocol scores label plus required direction for directed relations. Recall uses approved positives from the fixed recall frame, including missed candidates; precision counts every emitted prediction and treats predictions without approved gold as incorrect. Readiness requires all four labels to satisfy `n >= 60` and Wilson95 lower `>= 0.85`, plus typed zero observed and unreviewed false `DUPLICATE` counts and the cluster precision gate. Legacy scoring/report semantics remain available for historical reports, and legacy reports cannot authorize the quality protocol.

The v1 reader validates schema/version, dataset ID, frame roles, relative paths, file digests, row counts, pair IDs, cluster membership, and user-approved gold. The CLI has independent dev review and versioned report locks; the report lock binds the report to manifest/source fingerprints and predecessor digest. The bakeoff preflight recomputes quality metrics and cluster intervals from raw report evidence and fails closed when its new-protocol lock is missing or stale. A dev PASS alone cannot authorize a held-out decision.

## Cluster feasibility evidence for P3

The existing `harness.scripts.wilson.cluster_adjusted` route reports a lower bound of **0.5655175352168254** for five independent clusters with 12/12 conservative-precision successes in each cluster (`K=5`, `N=60`, route `cluster-floor`). That fails the retained `>= 0.85` cluster lower-bound gate even though every observation is correct. With 30 independent clusters and the same 12/12 pattern, the lower bound is **0.9894419431113063** (`K=30`, `N=360`, route `icc`).

Therefore P3 must not treat the plan's `>=5` cluster floor as sufficient for this gate. Retain all quality thresholds; before requesting human review, estimate per-label cluster feasibility and target at least 30 independent contributing clusters as a planning minimum, then compute the actual required count using the real cluster sizes and outcomes. If the corpus cannot support the gate, report the quantitative blocker and keep the protocol OFF; do not lower the threshold or count correlated pairs as independent clusters.

## Verification

- Focused P2 suite: `153 passed, 1 skipped`.
- Entire offline contract-graph suite: `296 passed, 1 skipped`.
- `py_compile` for the four owned modules: pass.
- `git diff --check` for owned files: pass.
- Provider requests: zero.
- Human review lock created or changed by this phase: no.

See [`verification-P2.json`](../../../plans/261010-2022-contract-graph-quality-recovery/artifacts/verification-P2.json) for commands and machine-readable evidence.
