from __future__ import annotations

import pytest

from evals.golden.spec import (
    ExpectedState,
    MutationSpec,
    expected_state_for,
)


@pytest.mark.parametrize(
    ("question_kind", "mutations", "expected"),
    [
        ("lookup", (), ExpectedState.ANSWERED),
        ("clause_lookup", (MutationSpec("non_conflicting_term"),), ExpectedState.ANSWERED),
        ("lookup", (MutationSpec("body_annex_conflict"),), ExpectedState.NEEDS_REVIEW),
        (
            "lookup",
            (MutationSpec("duplicate_name_different_tax_id"),),
            ExpectedState.NEEDS_REVIEW,
        ),
        ("lookup", (MutationSpec("overlapping_amendment"),), ExpectedState.NEEDS_REVIEW),
        ("lookup", (MutationSpec("missing_annex"),), ExpectedState.INSUFFICIENT_EVIDENCE),
        ("lookup", (MutationSpec("absent_information"),), ExpectedState.INSUFFICIENT_EVIDENCE),
        ("broad", (), ExpectedState.INSUFFICIENT_EVIDENCE),
        ("comparison", (MutationSpec("incomparable_quantities"),), ExpectedState.NOT_COMPARABLE),
        (
            "comparison",
            (MutationSpec("body_annex_conflict"), MutationSpec("missing_annex")),
            ExpectedState.NEEDS_REVIEW,
        ),
    ],
)
def test_expected_state_rules(
    question_kind: str,
    mutations: tuple[MutationSpec, ...],
    expected: ExpectedState,
) -> None:
    assert expected_state_for(question_kind, mutations) is expected


@pytest.mark.parametrize(
    ("question_kind", "mutations"),
    [
        ("unknown", ()),
        ("lookup", (MutationSpec("invented_mutation"),)),
    ],
)
def test_expected_state_rules_reject_unknown_inputs(
    question_kind: str,
    mutations: tuple[MutationSpec, ...],
) -> None:
    with pytest.raises(ValueError):
        expected_state_for(question_kind, mutations)


def test_catalog_states_come_from_rules() -> None:
    from evals.golden.catalog import CONTRACTS

    assert len(CONTRACTS) == 8
    assert {contract.contract_id for contract in CONTRACTS} == {
        f"G{number:02d}" for number in range(1, 9)
    }
    questions = [question for contract in CONTRACTS for question in contract.questions]
    assert len(questions) >= 84
    states = [question.expected_state for question in questions]
    assert states.count(ExpectedState.ANSWERED) >= 35
    assert states.count(ExpectedState.NEEDS_REVIEW) >= 15
    assert states.count(ExpectedState.INSUFFICIENT_EVIDENCE) >= 17
    assert states.count(ExpectedState.NOT_COMPARABLE) >= 4
    assert sum(question.kind == "comparison" for question in questions) >= 15
    assert sum(state is not ExpectedState.ANSWERED for state in states) / len(states) >= 0.2
    for question in questions:
        assert question.expected_state == expected_state_for(
            question.kind, question.mutations
        )


def test_contract_question_forms_are_distinct_after_term_normalization() -> None:
    from evals.golden.catalog import CONTRACTS

    signatures_by_contract: dict[str, set[str]] = {}
    for contract in CONTRACTS:
        signatures = set()
        terms = sorted(contract.features, key=len, reverse=True)
        for question in contract.questions:
            signature = question.text
            for term in terms:
                signature = signature.replace(term, "{term}")
            signatures.add(signature)
        signatures_by_contract[contract.contract_id] = signatures

    contract_ids = list(signatures_by_contract)
    for index, contract_id in enumerate(contract_ids):
        for other_id in contract_ids[index + 1 :]:
            assert signatures_by_contract[contract_id].isdisjoint(
                signatures_by_contract[other_id]
            ), f"{contract_id} and {other_id} reuse question forms"


def test_build_is_deterministic_and_manifest_hash_is_lf_normalized(tmp_path) -> None:
    from evals.golden.build_golden import build_golden

    first = tmp_path / "first"
    second = tmp_path / "second"
    assert build_golden(first) == 0
    assert build_golden(second) == 0
    first_files = sorted(path.relative_to(first) for path in first.rglob("*.*"))
    second_files = sorted(path.relative_to(second) for path in second.rglob("*.*"))
    assert first_files == second_files
    assert {
        path: (first / path).read_bytes() for path in first_files
    } == {path: (second / path).read_bytes() for path in second_files}

    import hashlib
    import json

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        payload = (first / entry["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(payload).hexdigest() == entry["sha256_lf"]
    assert manifest["spec_commit"] == "bdcb297e2522a589539c359b2f864d860754c660"


def test_snapshots_validate_spans_values_and_unit_floors(tmp_path) -> None:
    import json

    from jsonschema import Draft202012Validator

    from evals.golden.build_golden import SNAPSHOT_SCHEMA, build_golden

    assert build_golden(tmp_path) == 0
    validator = Draft202012Validator(json.loads(SNAPSHOT_SCHEMA.read_text(encoding="utf-8")))
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    questions = json.loads((tmp_path / "questions.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 8
    assert {entry["split"] for entry in manifest["files"]} == {"dev", "val", "holdout"}
    question_count = len(questions)
    states = [question["expected_state"] for question in questions]
    comparisons = [question for question in questions if question["comparison"]]
    required_count = sum(len(question["required_spans"]) for question in questions)
    value_count = sum(len(question["gold_values"]) for question in questions)
    assert question_count >= 84
    assert states.count("ANSWERED") >= 35
    assert states.count("NEEDS_REVIEW") >= 15
    assert states.count("INSUFFICIENT_EVIDENCE") >= 17
    assert states.count("NOT_COMPARABLE") >= 4
    assert len(comparisons) >= 15
    assert sum(state != "ANSWERED" for state in states) / question_count >= 0.2
    assert required_count >= 60
    assert value_count >= 60
    assert max(entry["pages"] for entry in manifest["files"]) >= 55
    assert sum(path.stat().st_size for path in tmp_path.rglob("*.*")) <= 3 * 1024 * 1024

    for entry in manifest["files"]:
        snapshot = json.loads((tmp_path / entry["path"]).read_text(encoding="utf-8"))
        assert list(validator.iter_errors(snapshot)) == []
        line_lookup = {
            line["line_id"]: line
            for page in snapshot["pages"]
            for line in page["lines"]
        }
        assert all(36 <= len(page["lines"]) <= 42 for page in snapshot["pages"])
        for question in (q for q in questions if q["contract_id"] == entry["contract_id"]):
            acceptable_ids = {
                (span["page_no"], line_id)
                for span in question["acceptable_spans"]
                for line_id in span["line_ids"]
            }
            required_ids = {
                (span["page_no"], line_id)
                for span in question["required_spans"]
                for line_id in span["line_ids"]
            }
            assert required_ids <= acceptable_ids
            for span in question["acceptable_spans"]:
                assert 1 <= len(span["line_ids"]) <= 3
                lines = [line_lookup[line_id] for line_id in span["line_ids"]]
                assert span["bbox"] == [
                    min(line["bbox"][0] for line in lines),
                    min(line["bbox"][1] for line in lines),
                    max(line["bbox"][2] for line in lines),
                    max(line["bbox"][3] for line in lines),
                ]
            for value in question["gold_values"]:
                source_span = next(
                    span for span in question["required_spans"]
                    if span["span_id"] == value["span_id"]
                )
                source_text = " ".join(line_lookup[line_id]["raw_text"] for line_id in source_span["line_ids"])
                assert value["raw"] in source_text


def test_split_is_by_contract_and_generated_assets_are_text_only(tmp_path) -> None:
    from evals.golden.build_golden import build_golden

    assert build_golden(tmp_path) == 0
    manifest = __import__("json").loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    splits = {entry["contract_id"]: entry["split"] for entry in manifest["files"]}
    assert {key for key, value in splits.items() if value == "dev"} == {"G01", "G02", "G03", "G05", "G08"}
    assert {key for key, value in splits.items() if value == "val"} == {"G04"}
    assert {key for key, value in splits.items() if value == "holdout"} == {"G06", "G07"}
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.png"))


def test_variant_seed_is_deterministic_and_differs(tmp_path) -> None:
    from evals.golden.build_golden import build_golden

    first = tmp_path / "one-a"
    repeat = tmp_path / "one-b"
    other = tmp_path / "two"
    assert build_golden(first, variant_seed=1) == 0
    assert build_golden(repeat, variant_seed=1) == 0
    assert build_golden(other, variant_seed=2) == 0
    first_questions = (first / "questions.json").read_bytes()
    assert first_questions == (repeat / "questions.json").read_bytes()
    assert first_questions != (other / "questions.json").read_bytes()
    assert (first / "snapshots/G01.json").read_bytes() != (other / "snapshots/G01.json").read_bytes()


def test_check_ignores_approval_and_build_preserves_or_resets_it(tmp_path, monkeypatch) -> None:
    from evals.golden.build_golden import approve, build_golden, check_golden

    monkeypatch.delenv("CI", raising=False)
    assert build_golden(tmp_path) == 0
    assert approve(approved_by="synthetic-test-reviewer", data_dir=tmp_path) == 0
    approved = __import__("json").loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert approved["approval"]["approved_by"] == "synthetic-test-reviewer"
    assert check_golden(tmp_path) == 0
    assert build_golden(tmp_path) == 0
    preserved = __import__("json").loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert preserved["approval"] == approved["approval"]

    questions_path = tmp_path / "questions.json"
    questions_path.write_text(questions_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert build_golden(tmp_path) == 2
    assert build_golden(tmp_path, reset_approval=True) == 0
    reset = __import__("json").loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert reset["approval"] is None


def test_approve_refuses_ci(monkeypatch, tmp_path) -> None:
    from evals.golden.build_golden import approve, build_golden

    assert build_golden(tmp_path) == 0
    monkeypatch.setenv("CI", "true")
    assert approve(approved_by="synthetic-test-reviewer", data_dir=tmp_path) == 2


def test_approval_timestamp_uses_utc_clock(tmp_path, monkeypatch) -> None:
    import json
    from datetime import datetime, timezone

    import evals.golden.build_golden as builder

    fixed = datetime(2030, 3, 4, 5, 6, 7, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(builder, "datetime", FrozenDateTime, raising=False)
    assert builder.build_golden(tmp_path) == 0
    assert builder.approve(approved_by="synthetic-test-reviewer", data_dir=tmp_path) == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["approval"]["approved_at"] == "2030-03-04T05:06:07Z"
