"""A small record whose FIELD units reach the LLM, for ST-067 budget/overload tests.

The shipped example snapshots make zero LLM calls, so they cannot exercise the
provider-failure paths. ``n1_fee`` normalizes locally (L0) and sorts first (units run in node_id order), so a
test can check that deterministic facts survive a later LLM failure.
"""

from __future__ import annotations

from fixtures.catalog import make_envelope, make_node, make_page, make_record

DOSSIER_ID = "d_llm_units"
LLM_FIELD_KEYS = ("party_a", "party_b", "service_scope")


def llm_units_record(*, egress_approved: bool = True):
    rec = make_record(
        case_id="ST067-LLM-UNITS",
        dossier=DOSSIER_ID,
        pages=[
            make_page(
                1,
                "Phí dịch vụ: 10.000.000 VND. Bên A: ABC Co. Bên B: XYZ Ltd. Phạm vi: bảo trì thang máy.",
            )
        ],
        nodes=[
            make_node("n1_fee", "FIELD", "Phí dịch vụ", "10.000.000 VND", structured_key="fee", structured_value="10.000.000 VND", order=1),
            make_node("n2_party_a", "FIELD", "Bên A", "ABC Co.", structured_key="party_a", structured_value="ABC Co.", order=2),
            make_node("n3_party_b", "FIELD", "Bên B", "XYZ Ltd.", structured_key="party_b", structured_value="XYZ Ltd.", order=3),
            make_node(
                "n4_scope", "FIELD", "Phạm vi", "bảo trì thang máy",
                structured_key="service_scope", structured_value="bảo trì thang máy", order=4,
            ),
        ],
    )
    rec.egress_approved = egress_approved
    return rec


def llm_units_envelope():
    return make_envelope(dossier=DOSSIER_ID)
