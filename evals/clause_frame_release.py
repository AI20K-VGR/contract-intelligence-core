"""Gate heldout độc lập; shared output chỉ có hashes và thống kê."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from evals.clause_frame_baseline import _get, _json_equal, _valid_path, _valid_sha256
from evals.clause_frame_scoring import PAIR_DISPOSITIONS, compare_units, validate_policy
from evals.unit_metrics import MetricSpec, UnitRecord, evaluate_metric

PROFILES = frozenset(
    {"SALES", "SUPPLY_SERVICE", "LEASE", "CONSTRUCTION_WORK", "EMPLOYMENT", "NDA"}
)
BADNESS = frozenset(
    {"key_wrong_definite", "pair_false_duplicate", "citation_extra", "value_fabricated"}
)
ZERO_ERRORS = frozenset({"pair_false_duplicate", "citation_extra", "value_fabricated"})
EXCLUSION_CATEGORIES = frozenset({"PAIR", "CLAUSE", "CITATION", "TIMELINE", "DOCUMENT"})
EXCLUSION_REASONS = frozenset(
    {
        "OUT_OF_SCOPE",
        "SOURCE_AMBIGUOUS",
        "OCR_UNREADABLE",
        "NOT_APPLICABLE",
        "DUPLICATE_SOURCE",
        "MISSING_SOURCE",
        "INSUFFICIENT_EVIDENCE",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayObservation:
    output: dict
    usage: dict


def _blocked(reason: str) -> dict:
    return {
        "quality_status": "BLOCKED",
        "release_status": "BLOCKED",
        "reasons": [reason],
    }


def _read(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("regular file required")
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError("JSON object required")
    return value, hashlib.sha256(raw).hexdigest()


def code_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "ai-service/app").rglob("*.py"))
    paths += [
        Path(__file__),
        root / "evals/clause_frame_scoring.py",
        root / "evals/clause_frame_baseline.py",
        root / "evals/unit_metrics.py",
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("aware timestamp required")
    return parsed


def _canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _principal() -> str:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        size = wintypes.DWORD(257)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not ctypes.WinDLL("advapi32", use_last_error=True).GetUserNameW(
            buffer, ctypes.byref(size)
        ):
            raise OSError("OS principal unavailable")
        return buffer.value
    import pwd

    return pwd.getpwuid(os.geteuid()).pw_name


def _denied_as_tuner(paths: Sequence[Path], tuner: str) -> bool:
    """Impersonate an actual OS principal; JSON 'denied' flags are never proof."""
    if (
        not isinstance(tuner, str)
        or not tuner.strip()
        or tuner.casefold() == _principal().casefold()
    ):
        return False
    if os.name != "nt":
        # A portable receipt is insufficient. Other OSes need an actual evaluator
        # execution adapter before measurement can be enabled.
        return False
    import ctypes
    from ctypes import wintypes

    password = os.environ.get("AI2_EVAL_TUNER_PASSWORD")
    if not password:
        return False
    domain, username = tuner.split("\\", 1) if "\\" in tuner else (".", tuner)
    token = wintypes.HANDLE()
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api.LogonUserW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    api.LogonUserW.restype = wintypes.BOOL
    api.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]
    api.ImpersonateLoggedOnUser.restype = wintypes.BOOL
    api.RevertToSelf.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    if not api.LogonUserW(username, domain, password, 2, 0, ctypes.byref(token)):
        return False
    try:
        if not api.ImpersonateLoggedOnUser(token):
            return False
        try:
            for path in paths:
                try:
                    # Opening proves read access without loading protected bytes.
                    with path.open("rb"):
                        return False
                except PermissionError:
                    continue
                except OSError:
                    return False
            return bool(paths)
        finally:
            if not api.RevertToSelf():
                raise RuntimeError("OS impersonation could not be reverted")
    finally:
        kernel.CloseHandle(token)


@contextmanager
def _reserve_private_output(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("preallocated private output required")
    with path.open("r+b") as stream:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if stream.read() != b"{}":
                raise ValueError("private output already used")
            yield stream
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def measure(
    manifest: Path,
    thresholds: Path,
    baseline: Path,
    freeze: Path,
    *,
    mode: str,
    replay: Callable | None = None,
    private_out: Path | None = None,
) -> dict:
    try:
        receipt, freeze_hash = _read(freeze)
    except (OSError, ValueError, TypeError):
        return _blocked("ISOLATION_OR_FREEZE_UNAVAILABLE")
    tuner = receipt.get("tuner")
    if receipt.get("evaluator") != _principal() or not _denied_as_tuner(
        (manifest, baseline), tuner
    ):
        return _blocked("ISOLATION_NOT_PROVEN")
    private_outputs = receipt.get("private_outputs")
    if (
        not isinstance(private_outputs, dict)
        or private_out is None
        or private_outputs.get(mode) != str(private_out)
        or not _denied_as_tuner((private_out,), tuner)
    ):
        return _blocked("PRIVATE_OUTPUT_ISOLATION_REQUIRED")
    try:
        if any(
            os.path.samefile(private_out, path)
            for path in (manifest, thresholds, baseline, freeze)
        ):
            return _blocked("PRIVATE_OUTPUT_INPUT_COLLISION")
        with _reserve_private_output(private_out) as stream:
            return _measure_inputs(
                manifest,
                thresholds,
                baseline,
                freeze,
                receipt,
                freeze_hash,
                mode=mode,
                replay=replay,
                private_out=private_out,
                private_stream=stream,
            )
    except (OSError, ValueError, TypeError):
        return _blocked("PRIVATE_OUTPUT_RESERVATION_FAILED")


def _measure_inputs(
    manifest,
    thresholds,
    baseline,
    freeze,
    receipt,
    freeze_hash,
    *,
    mode,
    replay,
    private_out,
    private_stream,
):
    tuner = receipt["tuner"]
    try:
        gold, gold_hash = _read(manifest)
        policy, policy_hash = _read(thresholds)
        old, baseline_hash = _read(baseline)
        source_hash = code_digest()
        expected = {
            "gold_hash": gold_hash,
            "policy_hash": policy_hash,
            "baseline_hash": baseline_hash,
            "candidate_code_hash": source_hash,
        }
        if (
            receipt.get("schema") != "ai2.clause-frame.candidate-freeze.v1"
            or receipt.get("approved_by") != "user"
            or not receipt.get("approval_ref")
            or receipt.get("retired") is not False
            or receipt.get("deblinded") is not False
            or any(receipt.get(key) != value for key, value in expected.items())
        ):
            return _blocked("CANDIDATE_FREEZE_OR_PIN_MISMATCH")
        frozen = _time(receipt["frozen_at"])
        if (
            not _time(policy["frozen_at"])
            <= frozen
            < _time(receipt["measurement_started_at"])
            or _time(policy["frozen_at"]) >= _time(receipt["tuning_started_at"])
            or _time(receipt["measurement_started_at"]) > datetime.now(timezone.utc)
            or frozen >= _time(receipt["holdout_first_visible_at"])
        ):
            return _blocked("FREEZE_ORDER_INVALID")
        expected_policy_pins = {
            name: receipt[name]
            for name in (
                "dev_baseline_hash",
                "dev_gold_hash",
                "split_hash",
                "historical_plan_a_card_hash",
            )
        }
        expected_policy_pins["scorer_hash"] = hashlib.sha256(
            Path(__file__).with_name("clause_frame_scoring.py").read_bytes()
        ).hexdigest()
        if (
            validate_policy(policy, expected_pins=expected_policy_pins)["status"]
            != "POLICY_VALIDATED"
        ):
            return _blocked("METRIC_POLICY_PIN_DRIFT")
        specs = release_specs(policy)
        people = [gold.get(key) for key in ("producer", "reviewer", "adjudicator")]
        if (
            gold.get("schema") != "ai2.clause-frame.gold.v1"
            or gold.get("split") != "heldout"
            or gold.get("approved") is not True
            or not gold.get("approval_ref")
            or not gold.get("consent_ref")
            or not all(isinstance(x, str) and x for x in people)
            or len(set(people)) != 3
            or gold.get("reviewer") != receipt["evaluator"]
        ):
            return _blocked("INDEPENDENT_APPROVED_HELDOUT_REQUIRED")
        profiles, sources, source_pins = {}, {}, {}
        dossiers = gold["dossiers"]
        if not isinstance(dossiers, list) or not dossiers:
            return _blocked("REAL_DOSSIERS_REQUIRED")
        for dossier in dossiers:
            identifier = dossier["id"]
            if (
                not isinstance(identifier, str)
                or not identifier
                or identifier in profiles
                or dossier.get("split") != "heldout"
                or dossier.get("source_kind") != "real"
                or dossier.get("profile") not in PROFILES
            ):
                return _blocked("REAL_DOSSIER_SCOPE_INVALID")
            path = Path(dossier["path"])
            if not _denied_as_tuner((path,), tuner):
                return _blocked("SOURCE_ISOLATION_NOT_PROVEN")
            source, source_pin = _read(path)
            if source_pin != dossier["sha256"]:
                return _blocked("SOURCE_HASH_DRIFT")
            profiles[identifier], sources[identifier] = dossier["profile"], source
            source_pins[path] = source_pin
        if not any(
            d.get("amendment_chain_verified") is True and d.get("amendment_review_ref")
            for d in dossiers
        ):
            return _blocked("REAL_AMENDMENT_CHAIN_REQUIRED")
        runtime_pins = receipt["runtime_pins"]
        required_pins = {
            "provider",
            "model",
            "prompt_hash",
            "budget_hash",
            "profile_hash",
        }
        if (
            not required_pins.issubset(runtime_pins)
            or not all(runtime_pins.get(key) for key in required_pins)
            or not all(
                _valid_sha256(runtime_pins[key])
                for key in ("prompt_hash", "budget_hash", "profile_hash")
            )
            or mode not in ("local-only", "enriched")
        ):
            return _blocked("FULL_RUNTIME_PINS_REQUIRED")
        profile_digests = {
            identifier: source["semantic_profile"]["digest"]
            for identifier, source in sources.items()
        }
        budgets = {
            identifier: {
                "context": source["semantic_profile"]["context_bounds"],
                "job": source["policy_flags"]["budget_limits"],
            }
            for identifier, source in sources.items()
        }
        if runtime_pins["profile_hash"] != _canonical(profile_digests) or runtime_pins[
            "budget_hash"
        ] != _canonical(budgets):
            return _blocked("RUNTIME_PROFILE_OR_BUDGET_DRIFT")
        if (
            old.get("schema") != "ai2.clause-frame.matched-baseline.v1"
            or old.get("split") != "heldout"
            or old.get("gold_hash") != gold_hash
            or old.get("policy_hash") != policy_hash
            or old.get("runtime_pins") != runtime_pins
            or not _valid_sha256(old.get("baseline_code_hash"))
        ):
            return _blocked("MATCHED_HELDOUT_BASELINE_REQUIRED")
        old_records = [UnitRecord(**unit) for unit in old["units"]]
        units = gold["units"]
        if not isinstance(units, list) or not units:
            return _blocked("INDEPENDENT_ELIGIBLE_UNITS_REQUIRED")
        identities = set()
        for unit in units:
            identity = (unit["metric"], unit["item_id"], unit["unit_id"])
            if (
                identity in identities
                or unit["metric"] not in {spec.metric for spec in specs}
                or unit["dossier_id"] not in profiles
                or unit.get("profile") != profiles[unit["dossier_id"]]
                or unit.get("predicate") != "exact"
                or not unit.get("evidence_ref")
                or not _valid_path(unit.get("path"))
                or not _valid_path(unit.get("identity_path"))
                or "expected" not in unit
                or "identity_expected" not in unit
            ):
                return _blocked("GOLD_UNIT_INVALID")
            identities.add(identity)
        if {(u.metric, u.item_id, u.unit_id) for u in old_records} != identities:
            return _blocked("BASELINE_ELIGIBILITY_MISMATCH")
        eligible_clusters = {
            (u["metric"], u["item_id"], u["unit_id"]): u["dossier_id"] for u in units
        }
        if any(
            u.split != "heldout"
            or u.cluster != eligible_clusters[(u.metric, u.item_id, u.unit_id)]
            for u in old_records
        ):
            return _blocked("BASELINE_CLUSTER_OR_SPLIT_MISMATCH")
        compare_units(old_records, old_records, specs)
        outputs, usage = {}, []
        replay = replay or production_replay
        for dossier in dossiers:
            observed = replay(sources[dossier["id"]], mode, runtime_pins, dossier)
            outputs[dossier["id"]] = (
                observed.output if isinstance(observed, ReplayObservation) else observed
            )
            if isinstance(observed, ReplayObservation):
                usage.append(observed.usage)
        predicted = []
        for unit in units:
            output = outputs[unit["dossier_id"]]
            found, value = _get(output, unit["path"])
            bound, identity = _get(output, unit["identity_path"])
            passed = (
                found
                and bound
                and _json_equal(identity, unit["identity_expected"])
                and _json_equal(value, unit["expected"])
            )
            predicted.append(
                UnitRecord(
                    unit["metric"],
                    unit["item_id"],
                    unit["unit_id"],
                    passed,
                    unit["dossier_id"],
                    split="heldout",
                )
            )
        pins = {
            manifest: gold_hash,
            thresholds: policy_hash,
            baseline: baseline_hash,
            freeze: freeze_hash,
            **source_pins,
        }
        if code_digest() != source_hash or any(
            hashlib.sha256(path.read_bytes()).hexdigest() != pin
            for path, pin in pins.items()
        ):
            return _blocked("INPUT_OR_CANDIDATE_DRIFT")
        if not _denied_as_tuner((manifest, baseline, private_out, *source_pins), tuner):
            return _blocked("ISOLATION_DRIFT_RETIRE_HOLDOUT")
        result = evaluate_release(
            old_records,
            predicted,
            policy,
            profiles=profiles,
            exclusions=gold.get("exclusions"),
        )
        result["pins"] = expected
        result["pins"]["candidate_freeze_hash"] = freeze_hash
        result["mode"] = mode
        keys = (
            "llm_calls_used",
            "embedding_tokens_used",
            "fallback_count",
            "elapsed_seconds",
            "prompt_tokens",
            "completion_tokens",
        )
        valid_usage = len(usage) == len(dossiers) and all(
            type(row.get(key)) in (int, float)
            and math.isfinite(row[key])
            and row[key] >= 0
            for row in usage
            for key in keys
        )
        result["cost_status"] = "MEASURED" if valid_usage else "NOT_MEASURED"
        if valid_usage:
            result["usage"] = {key: sum(row[key] for row in usage) for key in keys}
            result["usage"]["dossier_count"] = len(dossiers)
        private = {
            "schema": "ai2.clause-frame.private-result.v1",
            "pins": result["pins"],
            "mode": mode,
            "outputs": outputs,
            "units": [asdict(unit) for unit in predicted],
            "usage": usage,
        }
        private_stream.seek(0)
        private_stream.write(json.dumps(private, ensure_ascii=False).encode("utf-8"))
        private_stream.truncate()
        private_stream.flush()
        os.fsync(private_stream.fileno())
        return result
    except Exception:  # noqa: BLE001 - protected replay errors never escape into shared logs
        return _blocked("MEASUREMENT_INPUT_OR_REPLAY_INVALID")


def production_replay(
    source: dict, mode: str, pins: dict, dossier: dict
) -> ReplayObservation:
    started = time.monotonic()
    from evals.real_pipeline import _ensure_production_imports

    _ensure_production_imports()
    from app.contracts.wire import job_result_to_wire
    from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
    from app.pipeline.idp import run_idp
    from app.pipeline.runtime import ProcessingRuntime
    from app.tools.store import InMemorySnapshotStore

    request, adapted = adapt_be_ai2_processing_request(
        source, tenant_id=source["service_envelope"]["tenant_id"]
    )
    profile = request.semantic_profile
    if profile is None or profile.contract_type != dossier["profile"]:
        raise ValueError("frozen semantic profile required")
    # Cap/prompt/profile pins must describe the executable configuration, not labels.
    bounds = profile.context_bounds.model_dump(mode="json")
    from app.pipeline import frame_context

    if (
        pins["prompt_hash"]
        != hashlib.sha256(Path(frame_context.__file__).read_bytes()).hexdigest()
    ):
        raise ValueError("prompt implementation drift")
    if os.getenv("AI2_SEMANTIC_ENABLED", "").lower() != "true":
        raise ValueError("semantic producer disabled")
    server_caps = json.loads(os.environ.get("AI2_SEMANTIC_CONTEXT_CAPS", "{}"))
    if any(server_caps.get(key, -1) < value for key, value in bounds.items()):
        raise ValueError("server context caps missing or lower than freeze")
    llm = None
    if mode == "enriched":
        if (
            dossier.get("verified_anonymized") is not True
            or not dossier.get("anonymization_ref")
            or pins["provider"].rstrip("/") != "http://localhost:20128/v1"
        ):
            raise ValueError("verified anonymized local provider required")
        if not request.policy_flags.egress_allowed:
            raise ValueError("signed egress policy denies enrichment")
        if (
            request.policy_flags.budget_limits.max_llm_calls <= 0
            or profile.context_bounds.max_llm_calls <= 0
        ):
            raise ValueError("enriched mode requires frozen positive call budget")
        import httpx
        from app.llm.client import NineRouterClient

        key = os.environ.get("AI2_LLM_API_KEY", "")
        if not key:
            raise ValueError("local provider credential unavailable")
        with httpx.Client(timeout=10) as client:
            response = client.get(
                pins["provider"] + "/models", headers={"Authorization": f"Bearer {key}"}
            )
            response.raise_for_status()
            if pins["model"] not in {model["id"] for model in response.json()["data"]}:
                raise ValueError("frozen model unavailable")
        llm = NineRouterClient(
            base_url=pins["provider"],
            api_key=key,
            model=pins["model"],
            strong_model=pins["model"],
        )
    adapted.record.egress_approved = mode == "enriched"
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    runtime = ProcessingRuntime(
        egress_allowed=mode == "enriched",
        use_vector=False,
        max_processing_seconds=request.policy_flags.budget_limits.max_processing_seconds,
        max_llm_calls=request.policy_flags.budget_limits.max_llm_calls if llm else 0,
        max_embedding_tokens=0,
    )
    result = run_idp(
        adapted.record, adapted.envelope, llm=llm, store=store, runtime=runtime
    )
    wire = job_result_to_wire(result, request)
    if (
        not isinstance(wire.get("result"), dict)
        or wire["result"].get("semantic_extension") is None
    ):
        raise ValueError("semantic result not measured")
    usage = runtime.snapshot()
    usage["elapsed_seconds"] = time.monotonic() - started
    traces = llm.traces if llm else []
    for key in ("prompt_tokens", "completion_tokens"):
        usage[key] = (
            sum(trace[key] for trace in traces)
            if len(traces) == runtime.llm_calls_used
            and all(key in trace for trace in traces)
            else None
        )
    return ReplayObservation(wire, usage)


def paired_ablation(local: dict, enriched: dict) -> dict:
    """Evaluator-only paired comparison; return aggregate counts, never identities."""
    if (
        local.get("schema") != "ai2.clause-frame.private-result.v1"
        or enriched.get("schema") != local["schema"]
        or local.get("mode") != "local-only"
        or enriched.get("mode") != "enriched"
        or not local.get("pins")
        or local["pins"] != enriched.get("pins")
    ):
        raise ValueError("matched private experiments required")

    def records(value):
        rows = [UnitRecord(**row) for row in value["units"]]
        identities = {
            (row.metric, row.item_id, row.unit_id, row.cluster, row.split): row
            for row in rows
        }
        if (
            not rows
            or len(identities) != len(rows)
            or any(
                row.split != "heldout" or type(row.passed) is not bool for row in rows
            )
        ):
            raise ValueError("unique heldout units required")
        return identities

    before, after = records(local), records(enriched)
    if before.keys() != after.keys():
        raise ValueError("exact paired eligibility required")
    improvements = sum(
        not row.passed and after[key].passed for key, row in before.items()
    )
    regressions = sum(
        row.passed and not after[key].passed for key, row in before.items()
    )
    result = {
        "schema": "ai2.clause-frame.ablation.v1",
        "release_status": "BLOCKED",
        "paired_units": len(before),
        "improvements": improvements,
        "regressions": regressions,
        "pins": local["pins"],
        "recommendation": "RETAIN_LOCAL_ONLY"
        if regressions or not improvements
        else "HUMAN_REVIEW_REQUIRED",
        "cost_status": "NOT_MEASURED",
    }
    keys = (
        "llm_calls_used",
        "embedding_tokens_used",
        "fallback_count",
        "elapsed_seconds",
        "prompt_tokens",
        "completion_tokens",
    )
    usage = [local.get("usage"), enriched.get("usage")]
    if all(
        isinstance(rows, list)
        and rows
        and all(
            type(row.get(key)) in (int, float)
            and math.isfinite(row[key])
            and row[key] >= 0
            for row in rows
            for key in keys
        )
        for rows in usage
    ):
        result["cost_status"] = "MEASURED"
        result["usage_delta"] = {
            key: sum(row[key] for row in usage[1]) - sum(row[key] for row in usage[0])
            for key in keys
        }
    return result


def ablate_private(local: Path, enriched: Path, freeze: Path) -> dict:
    """Check actual ACL before opening either protected result."""
    try:
        receipt, freeze_hash = _read(freeze)
        expected = receipt["private_outputs"]
        paths = (local, enriched)
        if (
            receipt.get("evaluator") != _principal()
            or receipt.get("retired") is not False
            or receipt.get("deblinded") is not False
            or expected.get("local-only") != str(local)
            or expected.get("enriched") != str(enriched)
            or not _denied_as_tuner(paths, receipt.get("tuner"))
        ):
            return _blocked("ISOLATION_NOT_PROVEN")
        left, left_hash = _read(local)
        right, right_hash = _read(enriched)
        if any(
            result.get("pins", {}).get("candidate_freeze_hash") != freeze_hash
            for result in (left, right)
        ):
            return _blocked("ABLATION_FREEZE_MISMATCH")
        result = paired_ablation(left, right)
        if not _denied_as_tuner(paths, receipt.get("tuner")) or any(
            hashlib.sha256(path.read_bytes()).hexdigest() != digest
            for path, digest in (
                (local, left_hash),
                (enriched, right_hash),
                (freeze, freeze_hash),
            )
        ):
            return _blocked("ISOLATION_OR_INPUT_DRIFT")
        return result
    except Exception:  # noqa: BLE001 - protected data errors must stay private
        return _blocked("ABLATION_INPUT_INVALID")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("measure",))
    for name in ("manifest", "baseline", "thresholds", "freeze", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--split", choices=("heldout",), required=True)
    parser.add_argument("--mode", choices=("local-only", "enriched"), required=True)
    parser.add_argument("--private-out", type=Path)
    args = parser.parse_args(argv)
    if args.out.exists() or args.out.is_symlink():
        print(json.dumps(_blocked("OUTPUT_ALREADY_EXISTS")))
        return 2
    result = measure(
        args.manifest,
        args.thresholds,
        args.baseline,
        args.freeze,
        mode=args.mode,
        private_out=args.private_out,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        print(json.dumps(_blocked("OUTPUT_WRITE_REFUSED")))
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("quality_status", "release_status", "reasons")
            }
        )
    )
    return 2 if result["quality_status"] == "BLOCKED" else 0


def release_specs(policy: dict) -> tuple[MetricSpec, ...]:
    validated = validate_policy(policy)
    if validated["status"] != "POLICY_VALIDATED":
        raise ValueError("frozen policy invalid")
    names = {row["metric"] for row in policy["metrics"]}
    if not {f"pair_precision.{d}" for d in PAIR_DISPOSITIONS}.issubset(names):
        raise ValueError("all disposition precision specifications required")
    specs = []
    for row in policy["metrics"]:
        name = row["metric"]
        if row["direction"] != ("max" if name in BADNESS else "min"):
            raise ValueError("metric direction invalid")
        if row["predicate"] != "exact" or set(row["strata"]) != PROFILES:
            raise ValueError("exact predicate and six profile strata required")
        if row["minimum_units"] < 60:
            raise ValueError("Plan A minimum 60 units required")
        if (
            type(row.get("stratum_minimum_units")) is not int
            or row["stratum_minimum_units"] <= 0
        ):
            raise ValueError("frozen stratum minimum required")
        if name in ZERO_ERRORS and row["threshold"] != 0:
            raise ValueError("zero observed error tripwire cannot be relaxed")
        if name in {"citation_valid", "certainty_safety"} and row["threshold"] != 1:
            raise ValueError("hard invariant requires all units correct")
        threshold = 1 - row["threshold"] if name in BADNESS else row["threshold"]
        specs.append(
            MetricSpec(
                name,
                threshold,
                row["minimum_units"],
                max_failures=0 if name in ZERO_ERRORS else None,
            )
        )
    return tuple(specs)


def _aggregate_status(statuses: Sequence[str]) -> str:
    return next(
        (name for name in ("FAIL", "NOT_MEASURED", "UNDERPOWERED") if name in statuses),
        "PASS(point)",
    )


def evaluate_release(
    baseline: Sequence[UnitRecord],
    current: Sequence[UnitRecord],
    policy: dict,
    *,
    profiles: Mapping[str, str],
    exclusions: Sequence[Mapping[str, str]] | None = None,
) -> dict:
    """Score independently supplied units; no human authorization is inferred."""
    specs = release_specs(policy)
    declared = {spec.metric for spec in specs}
    if any(profile not in PROFILES for profile in profiles.values()):
        raise ValueError("unknown profile")
    for record in (*baseline, *current):
        if (
            record.split != "heldout"
            or record.cluster not in profiles
            or record.metric not in declared
        ):
            raise ValueError("heldout identity/profile/metric mismatch")
    regression = compare_units(baseline, current, specs)
    rows = []
    stratum_floors = {
        row["metric"]: row["stratum_minimum_units"] for row in policy["metrics"]
    }
    for spec in specs:
        overall = asdict(evaluate_metric(current, spec))
        overall.pop("units")
        overall["scope"] = "overall"
        if overall["status"] == "NOT_RUN":
            overall["status"] = "NOT_MEASURED"
        rows.append(overall)
        stratum_spec = replace(spec, unit_floor=stratum_floors[spec.metric])
        for profile in sorted(PROFILES):
            selected = [unit for unit in current if profiles[unit.cluster] == profile]
            result = asdict(evaluate_metric(selected, stratum_spec))
            result.pop("units")
            result["profile"] = profile
            if result["status"] == "NOT_RUN":
                result["status"] = "NOT_MEASURED"
            rows.append(result)
        for dossier, profile in sorted(profiles.items()):
            result = asdict(
                evaluate_metric(
                    [unit for unit in current if unit.cluster == dossier], stratum_spec
                )
            )
            result.pop("units")
            result.update(
                profile=profile,
                dossier_hash=hashlib.sha256(dossier.encode()).hexdigest(),
            )
            if result["status"] == "NOT_RUN":
                result["status"] = "NOT_MEASURED"
            rows.append(result)
    # DEC-3 eligible-pair counts use fixed gold units, not candidate key coverage.
    pair_counts = {}
    for unit in baseline:
        if unit.metric == "pair_false_duplicate":
            pair_counts[unit.cluster] = pair_counts.get(unit.cluster, 0) + 1
    pair_floor = sum(pair_counts.values()) >= 120
    quality = _aggregate_status([row["status"] for row in rows])
    reasons = ["MANUAL_RELEASE_EVIDENCE_REQUIRED"]
    if not pair_floor:
        reasons.append("DEC3_PAIR_SAMPLE_UNDERPOWERED")
        if quality == "PASS(point)":
            quality = "UNDERPOWERED"
    if regression.regressions:
        quality = "FAIL"
        reasons.append("EXACT_UNIT_REGRESSION")
    exclusion_counts: dict[str, int] = {}
    if exclusions is None:
        exclusion_status = "NOT_REPORTED"
        excluded_units = None
        reasons.append("ELIGIBILITY_EXCLUSIONS_NOT_REPORTED")
    else:
        eligible_identities = {
            (unit.metric, unit.item_id, unit.unit_id) for unit in baseline
        }
        excluded_identities: set[tuple[str, str, str]] = set()
        for exclusion in exclusions:
            required = {
                "metric",
                "item_id",
                "unit_id",
                "dossier_id",
                "category",
                "reason",
            }
            if (
                not isinstance(exclusion, Mapping)
                or set(exclusion) != required
                or not all(
                    isinstance(exclusion[key], str) and exclusion[key].strip()
                    for key in required
                )
            ):
                raise ValueError(
                    "exclusion identity and closed category/reason codes required"
                )
            if (
                exclusion["category"] not in EXCLUSION_CATEGORIES
                or exclusion["reason"] not in EXCLUSION_REASONS
            ):
                raise ValueError("unsupported exclusion code")
            identity = (exclusion["metric"], exclusion["item_id"], exclusion["unit_id"])
            if (
                identity in excluded_identities
                or identity in eligible_identities
                or exclusion["metric"] not in declared
                or exclusion["dossier_id"] not in profiles
            ):
                raise ValueError(
                    "excluded units must be unique and disjoint from eligible units"
                )
            excluded_identities.add(identity)
            key = f"{exclusion['category']}:{exclusion['reason']}"
            exclusion_counts[key] = exclusion_counts.get(key, 0) + 1
        exclusion_status = "REPORTED"
        excluded_units = len(excluded_identities)
    eligibility = {
        "eligible_units": len(
            {(unit.metric, unit.item_id, unit.unit_id) for unit in current}
        ),
        "eligible_pair_units": sum(
            unit.metric == "pair_false_duplicate" for unit in baseline
        ),
        "excluded_units": excluded_units,
        "exclusion_status": exclusion_status,
        "exclusions_by_category_reason": dict(sorted(exclusion_counts.items())),
    }
    return {
        "schema": "ai2.clause-frame.release-diagnostics.v1",
        "quality_status": quality,
        "release_status": "BLOCKED",
        "reasons": reasons,
        "regression_count": len(regression.regressions),
        "eligibility": eligibility,
        "strata": rows,
    }


if __name__ == "__main__":
    raise SystemExit(main())
