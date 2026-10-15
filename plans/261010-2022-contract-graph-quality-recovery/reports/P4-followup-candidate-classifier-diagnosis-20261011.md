# P4 follow-up: candidate ranking and classifier diagnosis

Date: 2026-10-11

## Scope and evidence

This is a dev-only follow-up. It reads the locked 32-document dev recall frame and approved labels, plus P4 classifier trial artifacts. No held-out inputs were read; all model calls used only dev pairs.

Candidate replay on the current dirty worktree reproduces the recorded baseline: **11/37** positive pairs at C/40. The current source fingerprint differs from the source fingerprint embedded in the original P4 run artifacts; this is a current-source replay, not a claim that the original P4 run used identical code.

The persisted candidate evaluation for the reviewed 600-row dev set shows that increasing deterministic C from k=40 to k=80 moves recall only from **11/37 to 13/37**; uncapped current C reaches **29/37**. Thus 8 positives are outside the current source union, while most of the recoverable positives sit below the cap. Raising k alone has weak marginal yield and substantially increases classifier workload.

## Candidate ranking probes

All probes kept the cap at 40 pairs/document and used only deterministic local ranking features. Coverage was:

| Ranking | Positive candidate coverage |
|---|---:|
| Current C/40 | 11/37 |
| Core article round-robin | 6/37 |
| 25 core + 15 exploratory | 7/37 |
| Pair-endpoint/article diversity penalty | 5/37 |
| Lexical Jaccard tie rank | 10/37 |
| Containment tie rank | 7/37 |
| IDF cosine tie rank | 11/37 |
| Node-gap tie rank | 12/37 |

None clears the dev candidate target. The best simple proximity probe previously recorded in `P4-root-cause-and-blockers.md` reached only 15/37. Therefore none of these heuristic variants is integrated or called a fix.

The candidate failure remains two distinct problems:

- **Source recall:** 8/37 approved positives are absent even with uncapped current candidates (5 `GENERAL_SPECIFIC`, 3 `REFERENCE`).
- **Ranking/cap:** 18 additional positives are generated but ranked outside C/40. The `SAME_ARTICLE` clique consumes quota, and stable document-position tie-breaking concentrates selections among early nodes.

The eight source misses were inspected by IDs and structural metadata without persisting or printing clause text. All are cross-article pairs. Three are adjacent or near-adjacent in structural order; five are farther apart (position gaps 4–14). A local C/40 quota grid at core shares 1.0, 0.9, and 0.8 stays at 11/37; 0.7 and below regress. A separate fixed-cap probe preserving C/40's first 32 and filling from cross-article neighboring eligible nodes reaches **12/37** only. None is a safe or sufficient runtime fix.

One bounded model-ranking probe, preregistered before calls, used `cx/gpt-5.5` only on the same 32-document dev frame and returned node-ID pairs without labels/spans. Top-40 selector alone covered **11/37**, equal to current C/40, but the offline union of selector and baseline lists covered **17/37** before applying a per-document 40-pair merge cap. A fixed-cap offline blend peaked at **15/37**. This suggests complementary ranking signal, but remains far below readiness and is not integrated into runtime. Two preregistered top-80 selector attempts are invalid/unscored: the first stopped at request 2 (2 requests, 108,416 tokens, 227.19 seconds), and the smaller-batch follow-up stopped at request 3 (3 requests, 107,334 tokens, 153.84 seconds); neither produced a metric and neither was retried. No held-out data was accessed.

## Classifier error pattern

Across the two baseline repeats and two checklist repeats on the same 20-pair diagnostic sample, the consistent observed errors include:

- The `CONFLICT` example is returned as `UNRELATED` in all four trials.
- Two `REFERENCE` examples are consistently returned as `UNRELATED` or `GENERAL_SPECIFIC`; a third has a missing/abstained result in all four trials.
- One `GENERAL_SPECIFIC` example has a missing/abstained result in all four trials.
- Checklist changed one `REFERENCE` prediction to the correct result in one repeat, but its two exact totals (15/20 and 14/20) do not improve the baseline worst-trial total (14/20).

This points to a relation-evidence and abstention/validation issue beyond prompt wording. Candidate generation still prevents the classifier from seeing 26/37 approved positives at C/40, so classifier work alone cannot clear end-to-end recall.

One abstention had a confirmed code-level cause: the reviewed `REFERENCE` pair `3eb7728ecd629f6b` was generated with `EXPLICIT_REF`, and `_decision` rejected every `REFERENCE` carrying that source. The sample's rejection counter confirms one `reference_explicit` rejection; its `REFERENCE` gold and direction were user-approved. This was a contradiction between the validator and the reviewed relation taxonomy, not an ungrounded-span case.

The guard was removed while retaining exact span grounding and required `referrer` direction. The follow-up reviewer found the prompt, candidate-source metadata, and public labeling guide disagreed about numbered references. Version `pairs-v12` now aligns these contracts: candidate provenance is passed explicitly to the classifier; the guide allows a numeric reference only when it resolves uniquely to the paired clause and the text confirms the relation; all references still require exact spans and direction. `pairs-labeler-v2` versions the labeling prompt. Its same exposed 20-pair dev diagnostic scored raw **15/20** against the previously approved gold (`REFERENCE` 2/3, `GENERAL_SPECIFIC` 1/3, `UNRELATED` 12/14; one false `DUPLICATE`; no validator rejections or abstentions). At least one scored GENERAL_SPECIFIC item contains a numbered citation that v12 now treats as REFERENCE evidence, so the gold taxonomy must be adjudicated before comparing v12 to v10's 16/20. This is not a quality PASS; v12 has not demonstrated an accuracy improvement. The v9/v10 reports preserve prior comparative measurements.

## Next measured remediation

A four-request `cx/gpt-5.5` semantic-selector diagnostic completed on the 32-document dev frame; see `P4-semantic-selector-batch4-preregistration.md` for its preregistration and score. Its fixed-cap merge reached only 15/37 and is not integrated. A separately preregistered top-80 follow-up failed invalid/unscored; see `P4-semantic-selector-top80-preregistration.md`. The local labeler config was supplied by the user and is stored only in ignored `.env`.

Classifier v12's raw score is 15/20 against old approved gold; a taxonomy change makes direct comparison to v10 invalid until affected gold is re-adjudicated. It still makes at least one REFERENCE miss, gets only 1/3 GENERAL_SPECIFIC under the old gold, and makes one false `DUPLICATE`. Candidate generation still misses 8/37 positives before classification, while current C/40 reaches 11/37; best fixed-cap tested ranking blend reaches 15/37, and the local adjacent-node blend reaches only 12/37. The requested recall problem is therefore **not resolved**. This corpus also has only 1 CONFLICT, 2 DUPLICATE, 27 GENERAL_SPECIFIC and 7 REFERENCE positives, below the preregistered per-label minimum of 60; no Wilson floor can be established. P4/P5 remain blocked; runtime remains OFF; the held-out lock and quality floors are unchanged.
