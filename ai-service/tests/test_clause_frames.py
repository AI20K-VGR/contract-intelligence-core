from __future__ import annotations

import pytest

from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
from app.pipeline.clause_keys import build_candidates, normalize_key


def evidence(snapshot="s1", text="Bên B phải thanh toán"):
    return Evidence("doc", snapshot, "p1/n1", text)


def slot(value, state="GROUNDED", snapshot="s1"):
    return Slot(value, state, (evidence(snapshot),))


def frame(**slots):
    return ClauseFrame("f1", "OBLIGATION", "SALES", "doc", "s1",
                       (evidence(),), tuple(slots.items()), "dossier")


def test_cross_snapshot_slot_is_rejected():
    with pytest.raises(ValueError, match="scope"):
        frame(actor=slot("B", snapshot="other"))


def test_grounded_slot_requires_evidence_and_value():
    with pytest.raises(ValueError):
        Slot("B", "GROUNDED", ())
    with pytest.raises(ValueError):
        slot(None)


def test_duplicate_slot_names_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        ClauseFrame("f1", "OBLIGATION", "SALES", "doc", "s1", (evidence(),),
                    (("actor", slot("B")), ("actor", slot("A"))), "dossier")


def test_missing_actor_never_becomes_any_party_definite_key():
    result = normalize_key(frame(action=slot("PAY")))
    assert result.certainty == "UNKNOWN"
    assert result.key is None
    assert "actor" in result.reason


@pytest.mark.parametrize("action", ["DO", "ANY_OBLIGATION", "invented"])
def test_generic_or_unknown_action_never_becomes_definite(action):
    result = normalize_key(frame(actor=slot("B"), action=slot(action)))
    assert result.key is None


def test_unknown_slot_never_becomes_definite_even_with_candidate_value():
    result = normalize_key(frame(actor=slot("B", "UNKNOWN"), action=slot("PAY")))
    assert result.certainty == "UNKNOWN"


def test_remedy_key_excludes_scope_and_requires_qualifier():
    remedy = ClauseFrame("r1", "REMEDY", "SALES", "doc", "s1", (evidence(),),
                         (("actor", slot("B")), ("action", slot("COMPENSATE")),
                          ("qualifier", slot("BREACH")), ("object_scope", slot("item1"))), "dossier")
    assert normalize_key(remedy).key == ("B", "COMPENSATE", "BREACH")


def test_negated_action_does_not_share_positive_key():
    positive = frame(actor=slot("B"), action=slot("PAY"), modality_negation=slot("REQUIRED"))
    negative = frame(actor=slot("B"), action=slot("PAY"), modality_negation=slot("PROHIBITED"))
    assert normalize_key(positive).key != normalize_key(negative).key


def test_unknown_keys_are_not_grouped_as_equal():
    from dataclasses import replace

    a = frame(action=slot("PAY"))
    b = replace(a, frame_id="f2")
    assert build_candidates((a, b)) == ()


def test_explicit_reference_keeps_unknown_pair_visible():
    from dataclasses import replace

    a = frame(action=slot("PAY"))
    b = replace(a, frame_id="f2")
    pairs = build_candidates((a, b), explicit_refs=(("f1", "f2"),))
    assert len(pairs) == 1
    assert pairs[0].sources == ("EXPLICIT_REF",)


def test_graph_rejects_cross_dossier_explicit_reference():
    from dataclasses import replace

    a = frame(action=slot("PAY"))
    b = replace(a, frame_id="f2", dossier_id="other")
    with pytest.raises(ValueError, match="dossier"):
        build_candidates((a, b), explicit_refs=(("f1", "f2"),))

def test_dossier_identity_cannot_be_omitted():
    with pytest.raises(TypeError):
        ClauseFrame("f", "OBLIGATION", "SALES", "doc", "s1", (evidence(),), ())


def test_whitespace_is_not_a_grounded_value():
    with pytest.raises(ValueError):
        slot("   ")

def test_parameter_key_does_not_require_invented_actor():
    from dataclasses import replace
    parameter = replace(frame(parameter=slot("unit_price")), family="PARAMETER")
    assert normalize_key(parameter).key == ("PARAMETER", "unit_price")


def test_definition_key_preserves_term():
    from dataclasses import replace
    definition = replace(frame(parameter=slot("Working day")), family="DEFINITION")
    assert normalize_key(definition).key == ("DEFINITION", "Working day")

def test_approved_alias_requires_matching_tenant_and_frozen_version():
    from app.pipeline.tenant_aliases import ApprovedAlias, ApprovedAliasSnapshot
    snapshot = ApprovedAliasSnapshot("tenant-a", 2, (ApprovedAlias("pay invoice", "PAY", "action", "p1"),))
    clause = frame(actor=slot("B"), action=slot("pay invoice"), modality_negation=slot("REQUIRED"))
    approved = normalize_key(clause, aliases=snapshot, tenant_id="tenant-a", alias_version=2)
    assert approved.key == ("B", "PAY", "OBLIGATION", "REQUIRED")
    assert approved.method == "TENANT_ALIAS"
    assert approved.alias_digest == snapshot.digest
    assert normalize_key(clause, aliases=snapshot, tenant_id="other", alias_version=2).key is None
    assert normalize_key(clause, aliases=snapshot, tenant_id="tenant-a", alias_version=1).key is None

def test_alias_snapshot_is_used_consistently_by_candidate_graph():
    from dataclasses import replace

    from app.pipeline.tenant_aliases import ApprovedAlias, ApprovedAliasSnapshot
    snapshot = ApprovedAliasSnapshot("t", 1, (ApprovedAlias("pay invoice", "PAY", "action", "p"),))
    left = frame(actor=slot("B"), action=slot("pay invoice"), modality_negation=slot("REQUIRED"))
    right = replace(frame(actor=slot("B"), action=slot("PAY"), modality_negation=slot("REQUIRED")), frame_id="f2")
    assert build_candidates((left, right), aliases=snapshot, tenant_id="t", alias_version=1)[0].sources == ("SAME_KEY",)

def test_pair_rejects_legal_winner_or_nonreview_state():
    from app.contracts.clause_frames import FramePair
    with pytest.raises(ValueError):
        FramePair("a", "b", "LEGAL_WINNER", "reason", (evidence(),), (evidence(),))
    with pytest.raises(ValueError):
        FramePair("a", "b", "DUPLICATE", "reason", (evidence(),), (evidence(),), "PASS")


def test_unknown_key_cannot_carry_definite_identity():
    from app.contracts.clause_frames import ClauseKey
    with pytest.raises(ValueError):
        ClauseKey(("B", "PAY"), "UNKNOWN", "uncertain")
