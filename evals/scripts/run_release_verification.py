"""Produce the P4 release evidence artifact without claiming business accuracy."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICE = ROOT / "ai-service"
if str(SERVICE) not in sys.path:
    sys.path.insert(0, str(SERVICE))

from evals.release_verification import (  # noqa: E402
    build_release_evidence,
    replay_grounded_query,
    replay_production,
    run_large_dossier_benchmark,
    run_mutation_matrix,
    validate_corpus_separation,
    validate_mutation_mapping,
    write_json,
)


def _registry() -> dict:
    try:
        proc = subprocess.run(
            ["node", "scripts/check-contract-registry.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {"status": "BLOCKED", "reason": f"registry command unavailable: {exc}"}
    return {"status": "PASS" if proc.returncode == 0 else "FAIL", "exit_code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def _card(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    from scripts.audit_candidate_corpus import build_manifest

    candidate = build_manifest()
    golden = _card(ROOT / "evals/corpus/golden_manifest.json")
    corpus = validate_corpus_separation(candidate, golden)
    scoring = {
        "status": "PASS",
        "schema_status": "PASS",
        "citation_status": "UNVERIFIED",
        "accuracy_status": "UNVERIFIED",
        "denominator": 0,
        "reason": "95 candidate cases are UNVERIFIED; no human-reviewed golden set is present",
    }

    handoff = SERVICE / "fixtures/eval_inputs/snapshots/ai1.full.v1.json"
    replays = [replay_production(handoff), replay_grounded_query(handoff)]
    mappings = _card(ROOT / "evals/mutation_mapping.json")["domains"]
    mutations = []
    try:
        contract_card = _card(ROOT / "evals/eval_config.json")
        query_card = _card(ROOT / "evals/cards/ai2_grounded_query.json")
        from evals.eval_types.ai2_contract_package.scorer import check_p0_gates as contract_gate
        from evals.eval_types.ai2_grounded_query.scorer import check_p0_gates as query_gate
        from evals.mutation_fixtures import apply_named_mutation, build_scorer_fixture, score_scorer_fixture

        for domain, card, gate in (("ai2_contract_package", contract_card, contract_gate), ("ai2_grounded_query", query_card, query_gate)):
            validate_mutation_mapping(card, mappings[domain])
            mutations.append({"domain": domain, **run_mutation_matrix(
                card,
                mappings[domain],
                gate,
                fixture_factory=build_scorer_fixture,
                mutation_applier=apply_named_mutation,
                result_scorer=score_scorer_fixture,
            )})
        mutation = {
            "status": "BLOCKED",
            "reason": "production mutation adapter is not wired; scorer-fixture observations are non-release evidence",
            "domains": mutations,
        }
    except Exception as exc:
        mutation = {"status": "BLOCKED", "reason": f"mutation mapping/configuration failed: {type(exc).__name__}: {exc}", "domains": mutations}

    workload = _card(ROOT / "evals/fixtures/large_dossier_workload.json")
    workload_path = ROOT / workload["payload"]
    performance = run_large_dossier_benchmark(workload_path, runs=3, limits=workload["limits"])
    performance["workload_fixture"] = "evals/fixtures/large_dossier_workload.json"
    live = {"status": "NOT_RUN", "reason": "live provider gate is opt-in and no approved credential run was requested"}
    evidence = build_release_evidence(
        corpus=corpus,
        scoring=scoring,
        replays=replays,
        mutation=mutation,
        performance=performance,
        registry=_registry(),
        live=live,
    )
    output = ROOT / "plans/260923-1023-ai2-completion-release/artifacts/verification-P4.json"
    write_json(output, evidence)
    print(json.dumps({"path": str(output), "release_verdict": evidence["release_verdict"], "accuracy_claim": evidence["accuracy_claim"]}, ensure_ascii=False, sort_keys=True))
    return 0 if evidence["release_verdict"] in {"PASS", "UNVERIFIED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
