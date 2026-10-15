# P4U implementation notes

- Bounded VALUE_MISMATCH expansion to at most eight following nodes per inverted posting. This prevents all-pairs materialization for each common term before top-K and records term/comparison counts for deterministic verification.
- Candidate generator version advanced to pairs-cand-v5 because candidate behavior changed.
- Pair-level abstained events now pass through recall diagnostics as classifier_abstained.
- Runtime pair coverage exposes abstentions separately. Candidate-set fallback stats include stable zero defaults.
- Added synthetic high-frequency-term bound test, abstention diagnostic test, and projection counter test.
- No evaluation corpus, held-out data, or model was accessed; no quality improvement claim; runtime remains OFF.
