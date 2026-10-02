from __future__ import annotations

import pytest

from evals.spikes.clause_key.mechanism import (
    Interval,
    Normalizer,
    decide,
    interval_relation,
    load_lexicon,
    parse_condition,
    parse_consequence,
    wilson,
)


@pytest.fixture(scope="module")
def norm() -> Normalizer:
    return Normalizer(load_lexicon())


def test_wilson_all_correct_lower_bound_matches_closed_form():
    lo, hi = wilson(30, 30)
    assert lo == pytest.approx(30 / (30 + 1.96**2), abs=1e-3)
    assert hi == pytest.approx(1.0)


def test_wilson_empty_sample_is_uninformative():
    assert wilson(0, 0) == (0.0, 1.0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # whole units: "quá 15 ngày" is the same threshold as "từ 16 ngày trở lên"
        ("quá 15 ngày", [Interval("days", 16, True, None, False)]),
        ("trên 30 ngày", [Interval("days", 31, True, None, False)]),
        ("từ 16 ngày trở lên", [Interval("days", 16, True, None, False)]),
        ("không quá 15 ngày", [Interval("days", None, False, 15, True)]),
        ("dưới 10 ngày", [Interval("days", None, False, 9, True)]),
        ("từ 5 đến 10 ngày", [Interval("days", 5, True, 10, True)]),
        ("quá 4 giờ", [Interval("hours", 5, True, None, False)]),
    ],
)
def test_parse_condition(text, expected):
    assert parse_condition(text) == expected


def test_parse_condition_unparseable_returns_none():
    assert parse_condition("trong thời gian hợp lý") is None


@pytest.mark.parametrize(
    ("a", "b", "rel"),
    [
        ("quá 15 ngày", "trên 15 ngày", "IDENTICAL"),
        ("quá 15 ngày", "từ 16 ngày trở lên", "IDENTICAL"),
        ("quá 15 ngày", "quá 30 ngày", "NESTED"),
        ("không quá 15 ngày", "quá 15 ngày", "DISJOINT"),
        ("từ 10 đến 20 ngày", "từ 15 đến 30 ngày", "OVERLAP"),
        ("quá 15 ngày", "quá 4 giờ", "DIFFERENT_DIM"),
    ],
)
def test_interval_relation(a, b, rel):
    assert interval_relation(parse_condition(a), parse_condition(b)) == rel


def test_interval_relation_unparsed_and_unconditional():
    assert interval_relation(None, None, unparsed_a=True) == "UNPARSED"
    assert interval_relation(None, None) == "IDENTICAL"
    assert interval_relation(None, parse_condition("quá 15 ngày")) == "NESTED"


@pytest.mark.parametrize(
    ("text", "ctype", "value", "base", "period"),
    [
        ("phạt 10.000.000 đồng", "PENALTY_FIXED", "10000000", None, None),
        ("bị phạt 20 triệu đồng", "PENALTY_FIXED", "20000000", None, None),
        ("phạt 8% giá trị phần nghĩa vụ bị vi phạm", "PENALTY_RATE", "8", "VIOLATED_PART", None),
        ("phạt 5% giá trị phần công việc vi phạm", "PENALTY_RATE", "5", "VIOLATED_PART", None),
        ("phạt 5% giá trị hợp đồng", "PENALTY_RATE", "5", "CONTRACT_VALUE", None),
        ("phạt 0,1% giá trị hợp đồng mỗi ngày chậm", "PENALTY_RATE", "0.1", "CONTRACT_VALUE", "PER_DAY"),
        ("phạt 1% giá trị hợp đồng cho mỗi tuần chậm", "PENALTY_RATE", "1", "CONTRACT_VALUE", "PER_WEEK"),
        ("bị phạt 4% giá trị hàng chậm giao", "PENALTY_RATE", "4", "OTHER", None),
        ("chịu lãi 0,05%/ngày trên số tiền chậm trả", "INTEREST", "0.05", "OTHER", "PER_DAY"),
        ("trả lãi theo lãi suất 12%/năm", "INTEREST", "12", None, "PER_YEAR"),
        ("có quyền đơn phương chấm dứt hợp đồng", "TERMINATION", None, None, None),
        ("bị xử lý kỷ luật sa thải", "TERMINATION", None, None, None),
        ("phải bồi thường toàn bộ thiệt hại", "DAMAGES", None, None, None),
        ("có quyền tạm dừng thanh toán", "SUSPENSION", None, None, None),
        ("khấu trừ 10% giá trị khối lượng chậm", "WITHHOLD", "10", "OTHER", None),
        ("giảm 5% phí dịch vụ", "WITHHOLD", "5", "OTHER", None),
        ("nhận khoản phạt tương đương 1 tháng tiền thuê", "PENALTY_FIXED", None, None, None),
    ],
)
def test_parse_consequence(text, ctype, value, base, period):
    c = parse_consequence(text)
    assert (c["type"], c["value"], c["base"], c["period"]) == (ctype, value, base, period)


def _remedy(bearer, action, qualifier=None, condition=None, consequence=None):
    return {
        "frame_type": "REMEDY",
        "spans": {
            "bearer_text": bearer,
            "action_text": action,
            "qualifier_text": qualifier,
            "condition_text": condition,
            "consequence_text": consequence,
        },
    }


def test_layer1_exact_alias(norm):
    r = norm.normalize(_remedy("Bên Bán", "giao hàng", "chậm"), "Bên Bán chậm giao hàng", {})
    assert r.key == ("SELLER", "DELIVER", "LATE")
    assert r.layer == 1


def test_layer2_core_token_containment(norm):
    r = norm.normalize(
        _remedy("Bên Bán", "chậm trễ trong việc bàn giao hàng hóa"), "…", {}
    )
    assert r.key == ("SELLER", "DELIVER", "LATE")
    assert r.layer == 2


def test_contract_party_alias_maps_ben_b(norm):
    ctx = {"parties": {"Bên B": "SELLER"}}
    r = norm.normalize(_remedy("Bên B", "giao hàng", "chậm"), "…", ctx)
    assert r.key[0] == "SELLER"


def test_passive_duoc_flips_bearer_for_pay(norm):
    text = "Bên Bán được thanh toán chậm quá 10 ngày thì Bên Mua chịu lãi 0,05%/ngày."
    r = norm.normalize(_remedy("Bên Bán", "thanh toán", "chậm"), text, {})
    assert r.key == ("BUYER", "PAY", "LATE")


def test_layer3_cross_reference_borrows_action(norm):
    ctx = {"articles": {"Điều 5": "Bên Bán phải giao hàng trước ngày 30/06/2026."}}
    r = norm.normalize(
        _remedy("Bên Bán", "vi phạm nghĩa vụ quy định tại Điều 5"), "…", ctx
    )
    assert r.key == ("SELLER", "DELIVER", None)
    assert r.layer == 3


def test_layer4_contract_local_definition(norm):
    ctx = {"definitions": {"vi phạm tiến độ": "việc Bên Bán giao hàng chậm so với lịch giao hàng"}}
    r = norm.normalize(_remedy("Bên Bán", "vi phạm tiến độ"), "…", ctx)
    assert r.key == ("SELLER", "DELIVER", "LATE")
    assert r.layer == 4


def test_layer5_enum_chooser_used_only_after_rules_fail(norm):
    calls = []

    def chooser(phrase, candidates):
        calls.append(phrase)
        return "DELIVER"

    r = norm.normalize(
        _remedy("Bên Bán", "không hoàn thành việc cung ứng đúng tiến độ"), "…", {}, chooser
    )
    assert calls == ["không hoàn thành việc cung ứng đúng tiến độ"]
    assert r.key[1] == "DELIVER"
    assert r.layer == 5


def test_layer6_backoff_when_qualifier_unknown(norm):
    r = norm.normalize(_remedy("Bên Bán", "giao hàng", "không như mong đợi"), "…", {})
    assert r.key == ("SELLER", "DELIVER", "?")
    assert r.layer == 6


def test_fold_only_rewrites_open_syllables():
    from evals.spikes.clause_key.mechanism import fold

    assert fold("hàng hoá") == "hàng hóa"
    assert fold("khoản 3.2") == "khoản 3.2"
    assert fold("Thuỷ") == "thủy"


def test_layer7_unmapped_without_chooser(norm):
    r = norm.normalize(_remedy("Bên cung cấp", "để thiết bị ngừng hoạt động"), "…", {})
    assert r.key is None
    assert r.layer == 7


def test_parameter_key_uses_param_and_object(norm):
    frame = {
        "frame_type": "PARAMETER",
        "spans": {"param_text": "đơn giá", "object_text": "hàng hóa A", "value_text": "200.000.000 đồng"},
    }
    r = norm.normalize(frame, "…", {})
    assert r.key == ("PARAM", "PRICE", "hàng hóa a")


def _f(key, condition, consequence, text=""):
    return {
        "key": key,
        "condition": parse_condition(condition) if condition else None,
        "condition_unparsed": False,
        "consequence": parse_consequence(consequence),
        "text": text,
    }


K = ("SELLER", "DELIVER", "LATE")


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, "trên 15 ngày", "phạt 20 triệu đồng"), "COMPARABLE_DIFFERENCE"),
        (_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, "quá 30 ngày", "có quyền đơn phương chấm dứt hợp đồng"), "GRADUATED"),
        (_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, "từ 16 ngày trở lên", "có quyền đơn phương chấm dứt hợp đồng"), "CUMULATIVE"),
        (_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, None, "phạt 0,1% giá trị lô hàng"), "COMPARABLE_DIFFERENCE"),
        (_f(K, "quá 15 ngày", "phạt 20.000.000 đồng"), _f(K, "quá 10 ngày", "phạt 12.000.000 đồng"), "COMPARABLE_DIFFERENCE"),
        (_f(K, "không quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, "quá 15 ngày", "phạt 20.000.000 đồng"), "GRADUATED"),
        (_f(K, "quá 20 ngày", "phạt 0,05% giá trị hợp đồng mỗi ngày"), _f(K, None, "phạt 1% giá trị hợp đồng mỗi tuần"), "COMPARABLE_DIFFERENCE"),
        (_f(K, None, "phạt 4% giá trị hàng chậm giao"), _f(K, None, "phạt 3% giá trị hợp đồng"), "NOT_COMPARABLE"),
        (_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, "quá 15 ngày", "phạt 10 triệu đồng"), "DUPLICATE"),
        (_f(K, None, "phạt 8% giá trị phần nghĩa vụ bị vi phạm"), _f(K, None, "phải bồi thường toàn bộ thiệt hại"), "CUMULATIVE"),
        (_f(K, None, "phạt 8% giá trị phần nghĩa vụ bị vi phạm"), _f(K, None, "phạt 5% giá trị hợp đồng"), "NOT_COMPARABLE"),
        (
            _f(K, None, "phạt 8% giá trị phần nghĩa vụ bị vi phạm"),
            _f(K, None, "phải bồi thường toàn bộ thiệt hại", text="Bên Mua chỉ được yêu cầu bồi thường thiệt hại"),
            "CONFLICT_CANDIDATE",
        ),
        (_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), _f(K, "quá 4 giờ", "phạt 20 triệu đồng"), "NOT_COMPARABLE"),
    ],
)
def test_decide(a, b, expected):
    assert decide(a, b) == expected


def test_decide_general_vs_specific():
    general = _f(("SELLER", "ANY_OBLIGATION", None), None, "phạt 8% giá trị phần nghĩa vụ bị vi phạm")
    specific = _f(K, "quá 15 ngày", "phạt 10.000.000 đồng")
    assert decide(general, specific) == "GENERAL_VS_SPECIFIC"


def test_decide_different_keys_not_compared():
    other = _f(("BUYER", "PAY", "LATE"), "quá 15 ngày", "phạt 10.000.000 đồng")
    assert decide(_f(K, "quá 15 ngày", "phạt 10.000.000 đồng"), other) is None


# --------------------------------------------------------------------------- lexicon v1 behaviour

@pytest.fixture(scope="module")
def norm1() -> Normalizer:
    from evals.spikes.clause_key.mechanism import LEXICON_V1_PATH

    return Normalizer(load_lexicon(LEXICON_V1_PATH))


def test_v1_negated_on_time_means_late(norm1):
    text = "Trường hợp hàng hóa không được Bên Bán giao đúng hạn, Bên Bán bị phạt 4%."
    r = norm1.normalize(_remedy("Bên Bán", "giao", consequence="bị phạt 4%"), text, {})
    assert r.key == ("SELLER", "DELIVER", "LATE")


def test_v1_qualifier_found_in_action_when_qualifier_span_is_a_condition(norm1):
    # LLM often returns action="chậm giao hàng", qualifier="quá 15 ngày"
    r = norm1.normalize(_remedy("Bên Bán", "chậm giao hàng", "quá 15 ngày"), "…", {})
    assert r.key == ("SELLER", "DELIVER", "LATE")


def test_v1_passive_with_negation_flips_bearer(norm1):
    text = "Trường hợp Bên Bán không được thanh toán đúng hạn, Bên Mua phải trả lãi."
    r = norm1.normalize(_remedy("Bên Bán", "thanh toán", consequence="Bên Mua phải trả lãi"), text, {})
    assert r.key == ("BUYER", "PAY", "LATE")


def test_v1_agent_after_duoc_does_not_flip(norm1):
    text = "Nếu Bên Mua không được Bên Bán giao hàng đúng hạn, Bên Bán phải chịu phạt 3%."
    r = norm1.normalize(_remedy("Bên Bán", "giao hàng", consequence="phải chịu phạt 3%"), text, {})
    assert r.key == ("SELLER", "DELIVER", "LATE")


def test_v1_consequence_as_action_falls_back_to_clause_scan(norm1):
    text = "Bên Mua chậm thanh toán quá 30 ngày thì phải trả lãi 0,05%/ngày."
    r = norm1.normalize(_remedy("Bên Mua", "phải trả lãi", consequence="phải trả lãi 0,05%/ngày"), text, {})
    assert r.key == ("BUYER", "PAY", "LATE")


def test_v1_profile_alias_ban_giao_in_construction(norm1):
    r = norm1.normalize(_remedy("Nhà thầu", "bàn giao", "chậm"), "…", {}, profile="CONSTRUCTION_WORK")
    assert r.key == ("CONTRACTOR", "COMPLETE_WORK", "LATE")


def test_v1_disclose_defaults_to_unauthorized_in_remedy(norm1):
    r = norm1.normalize(_remedy("Bên nhận", "để rò rỉ Thông tin mật"), "…", {})
    assert r.key == ("RECIPIENT", "DISCLOSE", "UNAUTHORIZED")


def test_v1_unknown_qualifier_marks_backoff_not_parent(norm1):
    r = norm1.normalize(_remedy("Bên Bán", "giao hàng", "không như mong đợi"), "…", {})
    assert r.key == ("SELLER", "DELIVER", "?")
    assert r.layer == 6


def test_v1_khoan_reference(norm1):
    ctx = {"articles": {"khoản 3.2": "Bên Mua thanh toán 70% giá trị hợp đồng."}}
    r = norm1.normalize(_remedy("Bên Mua", "vi phạm nghĩa vụ tại khoản 3.2"), "…", ctx)
    assert r.key == ("BUYER", "PAY", None)
    assert r.layer == 3


@pytest.mark.parametrize(
    ("param", "obj", "key"),
    [
        ("Giá trị tạm ứng", None, None),  # compound "giá trị" is not "giá"
        ("Giá trị của hợp đồng", None, ("PARAM", "CONTRACT_VALUE", None)),
        ("Nghĩa vụ bảo mật có hiệu lực trong thời hạn", None, ("PARAM", "CONFIDENTIALITY_PERIOD", None)),
        ("Giá trị hợp đồng", "hợp đồng này", ("PARAM", "CONTRACT_VALUE", None)),
    ],
)
def test_v1_parameter_keys(norm1, param, obj, key):
    frame = {"frame_type": "PARAMETER", "spans": {"param_text": param, "object_text": obj}}
    assert norm1.normalize(frame, "…", {}).key == key


def test_v1_enum_candidates_exclude_generic_obligation(norm1):
    seen = []

    def chooser(phrase, candidates):
        seen.extend(c["name"] for c in candidates)

    norm1.normalize(_remedy("Bên Bán", "làm điều gì đó lạ"), "…", {}, chooser)
    assert seen and "ANY_OBLIGATION" not in seen


def test_decide_backoff_key_is_never_grouped():
    a = _f(("SELLER", "DELIVER", "?"), None, "phạt 10.000.000 đồng")
    b = _f(("SELLER", "DELIVER", "?"), None, "phạt 20.000.000 đồng")
    assert decide(a, b) == "NEEDS_REVIEW_BACKOFF"


def test_v1_clause_scan_not_used_when_action_span_is_present_but_unmapped(norm1):
    text = "Người lao động tự ý bỏ việc từ 5 ngày làm việc liên tục trở lên thì bị xử lý kỷ luật sa thải."
    r = norm1.normalize(_remedy("Người lao động", "tự ý bỏ việc", consequence="bị xử lý kỷ luật sa thải"), text, {})
    assert r.key is None


@pytest.mark.parametrize(
    ("param", "obj", "key"),
    [
        ("Giá trị", "hợp đồng", ("PARAM", "CONTRACT_VALUE", None)),
        ("thời hạn", "Nghĩa vụ bảo mật", ("PARAM", "CONFIDENTIALITY_PERIOD", None)),
        ("Đơn giá", "sản phẩm X", ("PARAM", "PRICE", "sản phẩm x")),
    ],
)
def test_v1_parameter_split_across_param_and_object(norm1, param, obj, key):
    frame = {"frame_type": "PARAMETER", "spans": {"param_text": param, "object_text": obj}}
    assert norm1.normalize(frame, "…", {}).key == key


def test_v1_reference_found_outside_action_span(norm1):
    text = "Bên Mua vi phạm nghĩa vụ tại khoản 3.2 thì chịu phạt 8% giá trị phần nghĩa vụ bị vi phạm."
    ctx = {"articles": {"khoản 3.2": "Bên Mua thanh toán 70% giá trị hợp đồng."}}
    frame = _remedy("Bên Mua", "vi phạm nghĩa vụ", condition="tại khoản 3.2",
                    consequence="chịu phạt 8% giá trị phần nghĩa vụ bị vi phạm")
    assert norm1.normalize(frame, text, ctx).key == ("BUYER", "PAY", None)


def test_v1_default_qualifier_beats_backoff(norm1):
    r = norm1.normalize(_remedy("Bên nhận", "để rò rỉ Thông tin mật", "ra bên ngoài"), "…", {})
    assert r.key == ("RECIPIENT", "DISCLOSE", "UNAUTHORIZED")


@pytest.mark.parametrize(
    ("param", "obj", "key"),
    [
        # (a) the name is already complete: never borrow the object slot
        ("Giá trị tạm ứng", "giá trị hợp đồng", None),
        # (b) head "giá trị" modified by another noun is a different quantity
        ("Giá trị bảo hiểm công trình theo hợp đồng", None, None),
        # still matched: alias head at the end of the phrase
        ("Nghĩa vụ bảo mật có hiệu lực trong thời hạn", None, ("PARAM", "CONFIDENTIALITY_PERIOD", None)),
        ("được bảo hành trong thời gian", "Hàng hóa", ("PARAM", "WARRANTY_PERIOD", "hàng hóa")),
    ],
)
def test_v1_1_parameter_head_noun_rules(norm1, param, obj, key):
    frame = {"frame_type": "PARAMETER", "spans": {"param_text": param, "object_text": obj}}
    assert norm1.normalize(frame, "…", {}).key == key


# --------------------------------------------------------------------------- v2: document context (dev = held-out 1)

@pytest.fixture(scope="module")
def norm2() -> Normalizer:
    from evals.spikes.clause_key.mechanism import LEXICON_V2_PATH

    return Normalizer(load_lexicon(LEXICON_V2_PATH))


@pytest.mark.parametrize(
    ("bearer", "action", "qualifier", "key"),
    [
        ("một bên", "vi phạm bất kỳ điều khoản, điều kiện nào trong Hợp đồng", None, ("ANY_PARTY", "ANY_OBLIGATION", None)),
        ("một trong hai Bên", "vi phạm nghiêm trọng nghĩa vụ", None, ("ANY_PARTY", "ANY_OBLIGATION", None)),
        ("Bên Bán", "thực hiện nghĩa vụ quy định trong hợp đồng", "không", ("SELLER", "ANY_OBLIGATION", "NOT_PERFORMED")),
        ("một bên", "thực hiện hợp đồng", "bị chậm trễ", ("ANY_PARTY", "ANY_OBLIGATION", "LATE")),
        ("bên thuê", "trả tiền", "không", ("LESSEE", "PAY", "NOT_PERFORMED")),
    ],
)
def test_v2_generic_breach_and_bare_negation(norm2, bearer, action, qualifier, key):
    assert norm2.normalize(_remedy(bearer, action, qualifier), "…", {}).key == key


def test_v2_specific_action_beats_generic_breach(norm2):
    r = norm2.normalize(_remedy("Bên vi phạm", "vi phạm nghĩa vụ bảo mật"), "…", {}, profile="NDA")
    assert r.key == ("ANY_PARTY", "DISCLOSE", "UNAUTHORIZED")


@pytest.mark.parametrize(
    ("profile", "text", "key"),
    [
        ("SUPPLY_SERVICE", "Chậm giao thiết bị bị phạt 0,2% giá trị phần chậm giao cho mỗi ngày.", ("SUPPLIER", "DELIVER", "LATE")),
        ("SUPPLY_SERVICE", "Chậm khắc phục lỗi phần cứng bị phạt 0,1% giá trị phần lỗi cho mỗi ngày.", ("SUPPLIER", "WARRANT", "LATE")),
        ("CONSTRUCTION_WORK", "5.2. Phạt chậm phần xây lắp: 0,1%/ngày trên giá trị phần xây lắp chậm.", ("CONTRACTOR", "COMPLETE_WORK", "LATE")),
        ("CONSTRUCTION_WORK", "9.10. Thời hạn thanh toán không kéo dài vô hạn; chậm thanh toán phát sinh lãi theo thỏa thuận.", ("OWNER", "PAY", "LATE")),
    ],
)
def test_v2_implicit_bearer_from_profile(norm2, profile, text, key):
    frame = {"frame_type": "REMEDY", "spans": {"bearer_text": None, "action_text": None, "qualifier_text": None,
                                               "condition_text": None, "consequence_text": None}}
    assert norm2.normalize(frame, text, {}, profile=profile).key == key


def test_v2_nda_default_action_when_clause_names_none(norm2):
    text = "5.2. Ngoài bồi thường thiệt hại, bên vi phạm còn phải chịu phạt vi phạm số tiền ... đồng."
    r = norm2.normalize(_remedy("bên vi phạm", None, consequence="còn phải chịu phạt vi phạm số tiền ... đồng"),
                        text, {}, profile="NDA")
    assert r.key == ("ANY_PARTY", "DISCLOSE", "UNAUTHORIZED")


def test_v2_explicit_generic_bearer_is_not_overridden_by_profile_default(norm2):
    r = norm2.normalize(_remedy("Bên vi phạm", "giao hàng", "chậm"), "…", {}, profile="SALES")
    assert r.key[0] == "ANY_PARTY"


def test_v2_split_frame_with_two_consequences():
    from evals.spikes.clause_key.mechanism import split_consequences

    frame = _remedy("một bên", "vi phạm hợp đồng",
                    consequence="chịu phạt vi phạm với mức 8% giá trị hợp đồng và bồi thường cho bên kia toàn bộ thiệt hại")
    parts = split_consequences(frame)
    assert [parse_consequence(p["spans"]["consequence_text"])["type"] for p in parts] == ["PENALTY_RATE", "DAMAGES"]
    assert all(p["spans"]["action_text"] == "vi phạm hợp đồng" for p in parts)


def test_v2_single_consequence_is_not_split():
    from evals.spikes.clause_key.mechanism import split_consequences

    frame = _remedy("Bên Bán", "giao hàng", consequence="phải bồi thường toàn bộ thiệt hại và chi phí phát sinh")
    assert len(split_consequences(frame)) == 1


def test_v2_bare_not_performed_is_generic_breach(norm2):
    r = norm2.normalize(_remedy("Bên nào", "không thực hiện"), "…", {})
    assert r.key == ("ANY_PARTY", "ANY_OBLIGATION", "NOT_PERFORMED")


def test_v2_nda_bao_mat_and_bare_vi_pham(norm2):
    a = norm2.normalize(_remedy("Bên vi phạm", "bảo mật", "vi phạm"), "…", {}, profile="NDA")
    b = norm2.normalize(_remedy("bên vi phạm", "vi phạm"), "…", {}, profile="NDA")
    assert a.key == b.key == ("ANY_PARTY", "DISCLOSE", "UNAUTHORIZED")


def test_v2_bare_rate_per_period_is_penalty_rate():
    c = parse_consequence("0,2% (hai phần nghìn)/ngày")
    assert (c["type"], c["value"], c["period"]) == ("PENALTY_RATE", "0.2", "PER_DAY")
