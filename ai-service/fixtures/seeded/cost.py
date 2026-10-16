"""Live cost probe on the seeded dossiers (runs the configured LLM; local default is the router).

    python -m fixtures.seeded.cost        # per-dossier calls/tokens by stage + "COST_CALLS <total>"

Calls and tokens come from the client traces, grouped by the stage that made them, so a
cost change is attributable. Run it only against a cheap local model unless asked otherwise.
"""

from __future__ import annotations

import os
from collections import Counter

from app.llm.client import NineRouterClient
from app.pipeline.runtime import ProcessingRuntime
from fixtures.seeded import funnel as seeded_funnel
from fixtures.seeded.common import context_caps_env
from fixtures.seeded.score import DOSSIERS


def main() -> int:
    os.environ.setdefault("AI2_SEMANTIC_CONTEXT_CAPS", context_caps_env())
    by_stage: Counter[str] = Counter()
    real = ProcessingRuntime.complete_json

    def counted(self, client, system, user, **kwargs):
        before = self.llm_calls_used
        try:
            return real(self, client, system, user, **kwargs)
        finally:
            by_stage[kwargs.get("operation") or "unlabelled"] += self.llm_calls_used - before

    ProcessingRuntime.complete_json = counted
    total_calls = total_in = total_out = 0
    for module in [m for modules in DOSSIERS.values() for m in modules]:
        NineRouterClient.all_traces.clear()
        runtime = ProcessingRuntime(egress_allowed=True, max_processing_seconds=310, max_llm_calls=20)
        seeded_funnel.run(module.request(egress_allowed=True), llm=NineRouterClient(), runtime=runtime)
        tokens_in = sum(t.get("prompt_tokens") or 0 for t in NineRouterClient.all_traces)
        tokens_out = sum(t.get("completion_tokens") or 0 for t in NineRouterClient.all_traces)
        print(module.DOSSIER_ID, "calls", runtime.llm_calls_used, "tokens_in", tokens_in, "tokens_out", tokens_out,
              "issues", sorted({code for code, _ in runtime.issues}))
        total_calls += runtime.llm_calls_used
        total_in += tokens_in
        total_out += tokens_out
    print("by_stage", dict(by_stage))
    print("tokens_in", total_in, "tokens_out", total_out)
    print(f"COST_CALLS {total_calls}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
