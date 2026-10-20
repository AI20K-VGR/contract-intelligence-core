"""Clause-frame key normalization spike.

Measures one question: can a clause's verbatim spans be mapped to a canonical
comparison key reliably enough to group frames without inventing conflicts?

The LLM (when used) only copies spans and picks from a closed enum; everything
that builds keys and compares frames here is deterministic.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

LEXICON_PATH = Path(__file__).with_name("lexicon_v0.json")
LEXICON_V1_PATH = Path(__file__).with_name("lexicon_v1.json")
LEXICON_V2_PATH = Path(__file__).with_name("lexicon_v2.json")

# Old-style tone placement ("hoá") and new-style ("hóa") both occur in real
# contracts; fold to one form so aliases match either.
_TONE_FOLD = {
    "oá": "óa", "oà": "òa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oé": "óe", "oè": "òe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uý": "úy", "uỳ": "ùy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}

# Marker for "a qualifier was written but could not be resolved": such a key
# must never be grouped with anything, including other back-off keys.
BACKOFF = "?"

EnumChooser = Callable[[str, list[dict]], str | None]


def fold(text: str | None) -> str:
    s = unicodedata.normalize("NFC", text or "").casefold()
    for old, new in _TONE_FOLD.items():
        # Only open syllables ("hoá" → "hóa"); "khoản" must stay as is.
        s = re.sub(rf"{old}(?!\w)", new, s)
    return re.sub(r"\s+", " ", s).strip()


def load_lexicon(path: Path = LEXICON_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# --------------------------------------------------------------------------- conditions

@dataclass(frozen=True)
class Interval:
    """Closed-bound interval over whole units (days, hours, months)."""

    dim: str
    lo: float | None
    lo_incl: bool
    hi: float | None
    hi_incl: bool


_UNIT = r"(ngày|giờ|tuần|tháng)"
_DIM = {"ngày": ("days", 1), "tuần": ("days", 7), "giờ": ("hours", 1), "tháng": ("months", 1)}


def _dim(unit: str, n: str) -> tuple[str, float]:
    dim, mult = _DIM[unit]
    return dim, float(n) * mult


def parse_condition(text: str | None) -> list[Interval] | None:
    """Parse thresholds into closed whole-unit intervals; None when nothing parseable.

    Contract durations count whole units, so "quá 15 ngày" (> 15) and
    "từ 16 ngày trở lên" (>= 16) are normalized to the same interval.
    """
    s = fold(text)
    if not s:
        return None
    out: list[Interval] = []
    for m in re.finditer(rf"từ (\d+) đến (\d+) {_UNIT}", s):
        dim, lo = _dim(m.group(3), m.group(1))
        _, hi = _dim(m.group(3), m.group(2))
        out.append(Interval(dim, lo, True, hi, True))
    if not out:
        for m in re.finditer(rf"từ (\d+) {_UNIT} trở lên", s):
            dim, v = _dim(m.group(2), m.group(1))
            out.append(Interval(dim, v, True, None, False))
        for m in re.finditer(rf"(không quá|tối đa|trong vòng|dưới) (\d+) {_UNIT}", s):
            dim, v = _dim(m.group(3), m.group(2))
            out.append(Interval(dim, None, False, v - 1 if m.group(1) == "dưới" else v, True))
        for m in re.finditer(rf"(?<!không )(quá|trên|hơn|vượt quá) (\d+) {_UNIT}", s):
            dim, v = _dim(m.group(3), m.group(2))
            out.append(Interval(dim, v + 1, True, None, False))
    return out or None


def _contains(outer: Interval, inner: Interval) -> bool:
    lo_ok = outer.lo is None or (inner.lo is not None and inner.lo >= outer.lo)
    hi_ok = outer.hi is None or (inner.hi is not None and inner.hi <= outer.hi)
    return lo_ok and hi_ok


def _disjoint(a: Interval, b: Interval) -> bool:
    def before(x: Interval, y: Interval) -> bool:
        return x.hi is not None and y.lo is not None and x.hi < y.lo

    return before(a, b) or before(b, a)


def interval_relation(
    a: list[Interval] | None,
    b: list[Interval] | None,
    *,
    unparsed_a: bool = False,
    unparsed_b: bool = False,
) -> str:
    if unparsed_a or unparsed_b:
        return "UNPARSED"
    if a is None and b is None:
        return "IDENTICAL"
    if a is None or b is None:
        return "NESTED"  # an unconditional rule contains any conditioned one
    if len(a) != 1 or len(b) != 1:
        return "UNPARSED"
    x, y = a[0], b[0]
    if x.dim != y.dim:
        return "DIFFERENT_DIM"
    if x == y:
        return "IDENTICAL"
    if _disjoint(x, y):
        return "DISJOINT"
    if _contains(x, y) or _contains(y, x):
        return "NESTED"
    return "OVERLAP"


# --------------------------------------------------------------------------- consequences

_MONEY = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?)\s*(triệu|tỷ)?\s*(đồng|vnđ|vnd)")
_PCT = re.compile(r"(\d+(?:,\d+)?)\s*%")
_TYPE_CUES = (
    ("INTEREST", r"(?<!\w)lãi(?!\w)"),
    ("DAMAGES", r"bồi thường|đền bù|chịu (?:chi )?phí"),
    ("TERMINATION", r"chấm dứt|hủy bỏ hợp đồng|hủy hợp đồng|sa thải"),
    ("SUSPENSION", r"tạm ngừng|tạm dừng|tạm hoãn"),
    ("WITHHOLD", r"khấu trừ|giảm (?:\S+ )?\d|giữ lại"),
)
PENALTY_FAMILY = {"PENALTY_FIXED": "PENALTY", "PENALTY_RATE": "PENALTY"}


def _period(s: str) -> str | None:
    for period, pattern in (
        ("PER_DAY", r"/ngày|mỗi ngày"),
        ("PER_WEEK", r"/tuần|mỗi tuần"),
        ("PER_MONTH", r"/tháng|mỗi tháng"),
        ("PER_YEAR", r"/năm|mỗi năm"),
    ):
        if re.search(pattern, s):
            return period
    return None


def _base(s: str) -> str | None:
    """What a percentage is taken of."""
    if re.search(r"phần (?:\S+ ){0,4}?(?:bị )?vi phạm", s):
        return "VIOLATED_PART"
    if "giá trị hợp đồng" in s:
        return "CONTRACT_VALUE"
    if re.search(r"giá trị|số tiền|tiền|phí", s):
        return "OTHER"
    return None


def parse_consequence(text: str | None) -> dict:
    s = fold(text)
    ctype = next((t for t, pattern in _TYPE_CUES if re.search(pattern, s)), None)
    value = unit = base = period = None
    pct = _PCT.search(s)
    money = _MONEY.search(s)
    if pct:
        value, unit = str(Decimal(pct.group(1).replace(",", "."))), "%"
        base, period = _base(s[pct.end():]), _period(s)
        if ctype is None and ("phạt" in s or base or period):
            ctype = "PENALTY_RATE"  # a bare "0,2%/ngày" in a penalty clause
    elif money:
        raw = money.group(1).replace(".", "").replace(",", ".")
        mult = {"triệu": 10**6, "tỷ": 10**9}.get(money.group(2) or "", 1)
        value, unit, period = str(int(Decimal(raw) * mult)), "VND", _period(s)
        if ctype is None and "phạt" in s:
            ctype = "PENALTY_FIXED"
    elif ctype is None and "phạt" in s:
        ctype = "PENALTY_FIXED"  # penalty stated without a number ("tương đương 1 tháng tiền thuê")
    return {"type": ctype, "value": value, "unit": unit, "base": base, "period": period}


# --------------------------------------------------------------------------- normalization

@dataclass
class NormResult:
    key: tuple | None
    layer: int
    parts: dict = field(default_factory=dict)


_CONSEQUENCE_LIKE = re.compile(r"phạt|bồi thường|đền bù|(?<!\w)lãi(?!\w)|chấm dứt|hủy|sa thải|khấu trừ")
_CONDITION_LIKE = re.compile(r"^(?:quá|trên|dưới|từ|không quá|hơn|trong vòng|mỗi)?\s*\d|^(?:quá|trên|từ|dưới) \d")
_REF = re.compile(r"((?:điều|khoản) \d+(?:\.\d+)*)")


class Normalizer:
    def __init__(self, lexicon: dict):
        self.lex = lexicon
        self.stop = [fold(w) for w in lexicon["stopwords"]]
        self.actions = {
            name: sorted((fold(a) for a in spec["aliases"]), key=len, reverse=True)
            for name, spec in lexicon["actions"].items()
        }
        self.profile_actions = {
            profile: {n: [fold(a) for a in al] for n, al in table.items()}
            for profile, table in (lexicon.get("profile_aliases") or {}).items()
        }
        self.qualifiers = {n: [fold(a) for a in al] for n, al in lexicon["qualifiers"].items()}
        self.qualifier_patterns = {
            n: [re.compile(p) for p in pats] for n, pats in (lexicon.get("qualifier_patterns") or {}).items()
        }
        self.roles = {n: [fold(a) for a in al] for n, al in lexicon["roles"].items()}
        self.params = {n: [fold(a) for a in al] for n, al in lexicon["parameters"].items()}
        self.blocks = {fold(k): [fold(v) for v in vs] for k, vs in (lexicon.get("compounds_block") or {}).items()}
        self.object_none = {fold(o) for o in lexicon.get("object_as_none") or []}
        self.enum_exclude = set(lexicon.get("enum_exclude") or [])
        self.generic = {n for n, spec in lexicon["actions"].items() if spec.get("generic")}
        self.action_patterns = {
            n: [re.compile(p) for p in pats] for n, pats in (lexicon.get("action_patterns") or {}).items()
        }
        self.qualifier_bare = {fold(k): v for k, v in (lexicon.get("qualifier_bare") or {}).items()}
        self.default_bearer = lexicon.get("default_bearer") or {}
        self.profile_default_action = lexicon.get("profile_default_action") or {}

    # -- helpers
    def _strip(self, s: str) -> str:
        return " ".join(w for w in s.split(" ") if w not in self.stop)

    def _hit(self, alias: str, s: str) -> bool:
        for m in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", s):
            rest = s[m.start():]
            if not any(rest.startswith(c) for c in self.blocks.get(alias, [])):
                return True
        return False

    def _longest(self, table: dict[str, list[str]], s: str, *, exact: bool) -> str | None:
        best, best_len = None, 0
        for name, aliases in table.items():
            for a in aliases:
                hit = (s == a) if exact else self._hit(a, s)
                if hit and len(a) > best_len:
                    best, best_len = name, len(a)
        return best

    def _action(self, s: str, profile: str | None) -> tuple[str | None, int]:
        if not s:
            return None, 7
        local = self.profile_actions.get(profile or "", {})
        specific = {n: a for n, a in self.actions.items() if n not in self.generic}
        generic = {n: a for n, a in self.actions.items() if n in self.generic}
        # A named obligation ("vi phạm nghĩa vụ bảo mật", "... thanh toán") beats
        # the generic breach phrase that wraps it, whatever the alias lengths.
        for tables in ((local, specific), (generic,)):
            for exact, layer in ((True, 1), (False, 2)):
                for table in tables:
                    if not table:
                        continue
                    target = s if exact else self._strip(s)
                    hit = self._longest(table, target, exact=exact) or (
                        None if exact else self._longest(table, s, exact=False)
                    )
                    if hit:
                        return hit, layer
        for name, patterns in self.action_patterns.items():
            if any(p.search(s) for p in patterns):
                return name, 2
        return None, 7

    def _role(self, bearer: str, ctx: dict) -> str | None:
        b = fold(bearer)
        for alias, role in (ctx.get("parties") or {}).items():
            if fold(alias) == b:
                return role
        return self._longest(self.roles, b, exact=True) or self._longest(self.roles, b, exact=False)

    def _find_qualifier(self, s: str) -> str | None:
        if not s:
            return None
        if s in self.qualifier_bare:  # qualifier slot holds only "không"
            return self.qualifier_bare[s]
        for name, patterns in self.qualifier_patterns.items():
            if any(p.search(s) for p in patterns):
                return name
        return self._longest(self.qualifiers, s, exact=False)

    @staticmethod
    def _without(text: str, *spans: str | None) -> str:
        s = fold(text)
        for span in spans:
            if span:
                s = s.replace(fold(span), " ")
        return re.sub(r"\s+", " ", s).strip()

    # -- main
    def normalize(
        self,
        frame: dict,
        clause_text: str,
        ctx: dict,
        chooser: EnumChooser | None = None,
        profile: str | None = None,
    ) -> NormResult:
        spans = frame.get("spans") or {}
        if frame.get("frame_type") == "PARAMETER":
            return self._parameter(spans)

        action_text = fold(spans.get("action_text"))
        consequence_like = bool(_CONSEQUENCE_LIKE.search(action_text))
        action, layer = (None, 7) if consequence_like else self._action(action_text, profile)

        # Layer 3: an explicit reference ("tại Điều 5", "khoản 3.2") beats a
        # generic ANY_OBLIGATION match, since it names the obligation breached.
        scan = self._without(clause_text, spans.get("consequence_text"))
        if action in (None, "ANY_OBLIGATION"):
            ref = _REF.search(action_text) or _REF.search(
                " ".join(fold(spans.get(k)) for k in ("condition_text", "qualifier_text"))
            ) or (_REF.search(scan) if scan != "…" else None)
            if ref:
                for label, body in (ctx.get("articles") or {}).items():
                    if fold(label) == ref.group(1):
                        borrowed, _ = self._action(fold(body), profile)
                        if borrowed:
                            action, layer = borrowed, 3
                        break
        if action is None:  # layer 4: contract-local definitions
            for term, definition in (ctx.get("definitions") or {}).items():
                if fold(term) in action_text:
                    action, _ = self._action(fold(definition), profile)
                    if action:
                        layer = 4
                        action_text = f"{action_text} {fold(definition)}"
                        break
        if action is None and scan and scan != "…" and (not action_text or consequence_like):
            # Span missing or it holds the consequence: look in the clause itself.
            # An action span that is present but unmapped goes to the LLM/UNMAPPED
            # instead, so "tự ý bỏ việc" cannot borrow "làm việc" from elsewhere.
            action, _ = self._action(scan, profile)
            layer = 2 if action else 7
        if action is None and chooser is not None:  # layer 5: closed-enum LLM
            candidates = [
                {"name": n, "definition": s["definition"]}
                for n, s in self.lex["actions"].items()
                if n not in self.enum_exclude
            ]
            picked = chooser(spans.get("action_text") or "", candidates)
            if picked in self.actions and picked not in self.enum_exclude:
                action, layer = picked, 5
        bare = {fold(w) for w in self.lex.get("bare_generic_action") or []}
        if action is None and (not action_text or action_text in bare) and profile in self.profile_default_action:
            # e.g. an NDA penalty clause naming only "bên vi phạm": the only
            # obligation such a contract creates is confidentiality.
            action, layer = self.profile_default_action[profile], 4
        if action is None:
            return NormResult(None, 7, {"reason": "action unmapped"})

        bearer = self._role(spans.get("bearer_text") or "", ctx)
        if bearer is None:
            # No party named ("Chậm giao thiết bị bị phạt ..."): the obligor of
            # this action is fixed by the contract type.
            bearer = self.default_bearer.get(profile or "", {}).get(action, "ANY_PARTY")
        if self.lex["actions"][action].get("flip_on_passive") and self._is_passive(
            spans.get("bearer_text") or "", action, clause_text
        ):
            bearer = self.lex["counterparty"].get(bearer, bearer)

        qualifier_text = fold(spans.get("qualifier_text"))
        if _CONDITION_LIKE.search(qualifier_text):
            qualifier_text = ""  # a threshold landed in the qualifier slot
        qualifier = (
            self._find_qualifier(qualifier_text)
            or self._find_qualifier(action_text)
            or self._find_qualifier(scan if scan != "…" else "")
        )
        if qualifier is None:
            qualifier = self.lex["actions"][action].get("default_qualifier")
        if qualifier is None and qualifier_text:
            qualifier, layer = BACKOFF, max(layer, 6)
        return NormResult((bearer, action, qualifier), layer, {"bearer": bearer})

    def _is_passive(self, bearer_text: str, action: str, clause_text: str) -> bool:
        s, b = fold(clause_text), fold(bearer_text)
        if not b:
            return False
        for a in self.actions[action]:
            if re.search(rf"{re.escape(b)} (?:không |chưa )?được (?:[^\s]+ ){{0,3}}?{re.escape(a)}", s):
                return True
        return False

    def _parameter(self, spans: dict) -> NormResult:
        p = fold(spans.get("param_text"))
        obj = fold(spans.get("object_text")) or None
        param, layer = self._param_name(p)
        if param is None and obj and len(p.split()) <= 2:
            # "Giá trị" + "hợp đồng": a bare head noun means the name was split
            # across two slots. A complete name ("Giá trị tạm ứng") never borrows
            # the object, which may just echo the value ("30% giá trị hợp đồng").
            for joined in (f"{obj} {p}", f"{p} {obj}"):
                param, layer = self._param_name(joined)
                if param is not None:
                    obj = None
                    break
        if param is None:
            return NormResult(None, 7, {"reason": "parameter unmapped"})
        if obj in self.object_none:
            obj = None
        return NormResult(("PARAM", param, obj), layer)

    def _param_name(self, p: str) -> tuple[str | None, int]:
        stripped = self._strip(p)
        param, layer = self._longest(self.params, p, exact=True), 1
        if param is None:
            param, layer = self._longest(self.params, stripped, exact=True), 1
        if param is None:
            param, layer = self._longest(self.params, stripped, exact=False), 2
        if param is None:  # every word of an alias present, any order
            words = p.split()
            for name, aliases in self.params.items():
                if any(
                    len(a.split()) > 1 and set(a.split()) <= set(words) and self._head_free(a.split(), words)
                    for a in aliases
                ):
                    param, layer = name, 2
                    break
        return param, layer

    def _head_free(self, alias: list[str], words: list[str]) -> bool:
        """The alias head (first two syllables) must not be modified by a foreign noun.

        Vietnamese noun phrases are head-first: in "giá trị bảo lãnh … hợp đồng"
        the head "giá trị" belongs to "bảo lãnh", so it is not "giá trị hợp đồng".
        """
        head = alias[:2]
        for i in range(len(words) - 1):
            if words[i:i + 2] == head:
                nxt = words[i + 2] if i + 2 < len(words) else None
                if nxt is None or nxt in alias or nxt in self.stop:
                    return True
        return False


_SPLIT = re.compile(r",?\s+(?:và|đồng thời)\s+")


def split_consequences(frame: dict) -> list[dict]:
    """One frame per consequence: "phạt 8% ... và bồi thường ..." -> two frames.

    Split only when at least two parts each carry a recognisable consequence
    type, so "bồi thường thiệt hại và chi phí phát sinh" stays whole.
    """
    spans = frame.get("spans") or {}
    text = spans.get("consequence_text")
    if frame.get("frame_type") != "REMEDY" or not text:
        return [frame]
    parts = [p for p in _SPLIT.split(text) if p.strip()]
    typed = [p for p in parts if parse_consequence(p)["type"]]
    if len(typed) < 2 or len({parse_consequence(p)["type"] for p in typed}) < 2:
        return [frame]
    return [{**frame, "spans": {**spans, "consequence_text": p}} for p in typed]


# --------------------------------------------------------------------------- comparison

_EXCLUSIVE = re.compile(r"chỉ được|chỉ có quyền|chỉ áp dụng|duy nhất|thay cho|thay thế cho")
_ADDITIVE = {"PENALTY_FIXED", "PENALTY_RATE", "DAMAGES", "INTEREST"}


def decide(a: dict, b: dict) -> str | None:
    """Classify the difference between two normalized frames; None = not compared."""
    ka, kb = a["key"], b["key"]
    if ka is None or kb is None:
        return None
    if BACKOFF in ka or BACKOFF in kb:
        same_head = ka[:2] == kb[:2]
        return "NEEDS_REVIEW_BACKOFF" if same_head else None
    if ka != kb:
        general = {k for k in (ka, kb) if k[1] == "ANY_OBLIGATION"}
        if len(general) == 1 and (ka[0] == kb[0] or "ANY_PARTY" in (ka[0], kb[0])):
            return "GENERAL_VS_SPECIFIC"
        return None

    rel = interval_relation(
        a["condition"], b["condition"],
        unparsed_a=a.get("condition_unparsed", False),
        unparsed_b=b.get("condition_unparsed", False),
    )
    if rel == "UNPARSED":
        return "NEEDS_REVIEW_UNPARSED"
    if rel == "DIFFERENT_DIM":
        return "NOT_COMPARABLE"

    ca, cb = a["consequence"], b["consequence"]
    ta, tb = ca["type"], cb["type"]
    fa, fb = PENALTY_FAMILY.get(ta, ta), PENALTY_FAMILY.get(tb, tb)
    exclusive = bool(_EXCLUSIVE.search(fold(a.get("text")))) or bool(_EXCLUSIVE.search(fold(b.get("text"))))

    if ta == tb:
        if ca["base"] and cb["base"] and ca["base"] != cb["base"]:
            return "NOT_COMPARABLE"
        if rel == "DISJOINT":
            return "GRADUATED"
        if ca["value"] == cb["value"] and rel == "IDENTICAL" and ca["period"] == cb["period"]:
            return "DUPLICATE"
        return "COMPARABLE_DIFFERENCE"
    if fa == fb:  # fixed vs rate penalty: two penalty regimes for one breach
        return "GRADUATED" if rel == "DISJOINT" else "COMPARABLE_DIFFERENCE"
    if exclusive:
        return "CONFLICT_CANDIDATE"
    if ta in _ADDITIVE and tb in _ADDITIVE:
        return "CUMULATIVE"
    return "GRADUATED" if rel in ("DISJOINT", "NESTED") else "CUMULATIVE"
