import pytest

from app.reasoning.ask_intent import parse_ask


@pytest.mark.parametrize(
    "question",
    [
        # Staging E2E 16/10 (#121): both were answered by verbatim lookup, never by the LLM.
        "Mỗi đợt thanh toán bao nhiêu phần trăm giá trị hợp đồng?",
        "Tóm tắt các nghĩa vụ thanh toán của Bên A; phụ lục có quy định khác không?",
    ],
)
def test_questions_that_need_synthesis_go_to_the_reasoning_layer(question):
    assert parse_ask(question)["type"] == "unscoped"


def test_compare_questions_keep_their_compare_route():
    assert parse_ask("So sánh thời hạn bảo hành giữa hợp đồng và phụ lục")["type"] == "compare"


@pytest.mark.parametrize(
    "question",
    [
        "Hồ sơ có bao nhiêu phụ lục?",
        "Có những phụ lục nào?",
        "Danh sách phụ lục",
    ],
)
def test_questions_about_the_annexes_themselves_still_list_them(question):
    assert parse_ask(question)["type"] == "annex_list"


def test_plain_term_lookup_is_unchanged():
    assert parse_ask("Thời hạn thanh toán là bao lâu?")["type"] == "lookup_term"


def test_synthesis_question_retrieves_every_installment_clause():
    import os

    from fixtures.seeded.common import context_caps_env

    os.environ.setdefault("AI2_SEMANTIC_CONTEXT_CAPS", context_caps_env())
    from app.reasoning.l1_retrieval import L1Retrieval
    from app.tools.gateway import ToolGateway
    from app.tools.store import InMemorySnapshotStore
    from fixtures.seeded import funnel, hd_test_2026_005

    f = funnel.run(hd_test_2026_005.request())
    store = InMemorySnapshotStore()
    store.put(f.record)
    query = "Mỗi đợt thanh toán bao nhiêu phần trăm giá trị hợp đồng?"
    hits = L1Retrieval(ToolGateway(store)).run(f.envelope, {**parse_ask(query)})["hits"]
    ids = {h.get("node_id") for h in hits}
    assert {f.node(label) for label in ("5.1. Đợt 1", "5.2. Đợt 2", "5.3. Đợt 3")} <= ids
