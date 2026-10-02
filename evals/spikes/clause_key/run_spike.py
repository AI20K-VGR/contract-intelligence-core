"""Run the clause-key spike and report key/pair/decision metrics with Wilson CIs.

Modes:
  rules     gold spans, deterministic ladder only (layers 1-4, 6, 7); offline
  llm-enum  gold spans, plus layer 5 (closed-enum LLM, 2 votes must agree)
  llm-full  LLM copies spans itself (verbatim-checked), then llm-enum ladder

Usage (repo root):
  ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.run_spike --mode rules
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from evals.spikes.clause_key.mechanism import (
    _CONDITION_LIKE,
    BACKOFF,
    LEXICON_PATH,
    Normalizer,
    decide,
    fold,
    load_lexicon,
    parse_condition,
    parse_consequence,
    split_consequences,
    wilson,
)

HERE = Path(__file__).parent
REPO = HERE.parents[2]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------------------- LLM hooks

def _load_env(path: Path) -> None:
    """Load KEY=VALUE lines without overriding variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _client():
    _load_env(REPO / "ai-service" / ".env")
    sys.path.insert(0, str(REPO / "ai-service"))
    from app.llm.client import NineRouterClient

    client = NineRouterClient()
    if not client.configured():
        raise SystemExit("LLM not configured (AI2_LLM_BASE_URL / AI2_LLM_API_KEY)")
    return client


def make_chooser(client, votes: int = 2):
    system = (
        "Bạn phân loại một cụm từ trong hợp đồng vào ĐÚNG MỘT hành vi trong danh sách cho trước. "
        "Nếu không hành vi nào đúng nghĩa, trả NONE. Không giải thích. "
        'Trả JSON: {"action": "<NAME hoặc NONE>"}'
    )

    def choose(phrase: str, candidates: list[dict]) -> str | None:
        listing = "\n".join(f"- {c['name']}: {c['definition']}" for c in candidates)
        user = f"Danh sách hành vi:\n{listing}\n\nCụm từ: \"{phrase}\""
        picks = []
        for _ in range(votes):
            try:
                picks.append(str(_with_retry(lambda: client.complete_json(system, user)).get("action") or "NONE"))
            except Exception:  # noqa: BLE001 - a failed vote counts as NONE
                picks.append("NONE")
        return picks[0] if len(set(picks)) == 1 and picks[0] != "NONE" else None

    return choose


EXTRACT_SYSTEM_V0 = (
    "Bạn là bộ trích xuất điều khoản hợp đồng. Mỗi mệnh đề chế tài (vi phạm → hậu quả) hoặc "
    "mệnh đề tham số (giá, thời hạn...) là một frame. QUY TẮC: mọi trường phải là đoạn CHÉP "
    "NGUYÊN VĂN từ điều khoản, không diễn giải, không thêm chữ. Không có thì null.\n"
    'REMEDY: {"frame_type":"REMEDY","bearer_text","action_text","qualifier_text",'
    '"condition_text","consequence_text"} — bearer là bên VI PHẠM.\n'
    'PARAMETER: {"frame_type":"PARAMETER","param_text","object_text","value_text"}\n'
    'Trả JSON: {"frames": [...]}'
)


# v1: field definitions + two worked examples taken from clauses_dev.jsonl (never test).
EXTRACT_SYSTEM_V1 = """Bạn là bộ trích xuất điều khoản hợp đồng tiếng Việt.
Mỗi mệnh đề CHẾ TÀI (hành vi vi phạm → hậu quả) là một frame REMEDY; mỗi mệnh đề nêu một
giá trị (giá, tiền thuê, lương, thời hạn...) là một frame PARAMETER.
QUY TẮC CHUNG: mọi trường là đoạn CHÉP NGUYÊN VĂN từ điều khoản; không diễn giải, không thêm chữ; không có thì null.

REMEDY — ý nghĩa từng trường:
- bearer_text: bên VI PHẠM (bên bị áp chế tài), không phải bên được hưởng.
- action_text: CHỈ hành vi/nghĩa vụ bị vi phạm (vd "giao hàng", "thanh toán", "tiết lộ Thông tin mật").
  KHÔNG đưa vào đây hậu quả (phạt, bồi thường, lãi, chấm dứt...) và KHÔNG đưa từ chỉ mức độ (chậm, thiếu...).
- qualifier_text: CÁCH vi phạm (vd "chậm", "không đúng hạn", "không đủ số lượng", "trái phép"). KHÔNG chứa con số.
- condition_text: ngưỡng có số (vd "quá 15 ngày", "từ 11 ngày trở lên").
- consequence_text: hậu quả (vd "chịu phạt 7.000.000 đồng", "có quyền hủy hợp đồng").
PARAMETER: param_text (tên đại lượng, vd "Đơn giá"), object_text (đối tượng, vd "sản phẩm X"), value_text.

Ví dụ 1 — "Bên Mua thanh toán quá hạn trên 10 ngày thì phải chịu phạt 2.000.000 đồng."
{"frames":[{"frame_type":"REMEDY","bearer_text":"Bên Mua","action_text":"thanh toán","qualifier_text":"quá hạn","condition_text":"trên 10 ngày","consequence_text":"phải chịu phạt 2.000.000 đồng"}]}
Ví dụ 2 — "Đơn giá sản phẩm X: 12.000.000 đồng/chiếc."
{"frames":[{"frame_type":"PARAMETER","param_text":"Đơn giá","object_text":"sản phẩm X","value_text":"12.000.000 đồng/chiếc"}]}

Trả JSON: {"frames": [...]}"""
# v2: rules learnt on held-out 1 (dev for v2); example 3 is a held-out 1 clause.
EXTRACT_SYSTEM_V2 = EXTRACT_SYSTEM_V1.replace(
    "Trả JSON: {\"frames\": [...]}",
    """QUY TẮC BỔ SUNG:
- Mỗi HẬU QUẢ là một frame riêng (phạt / bồi thường / lãi / chấm dứt / tạm ngừng), lặp lại bearer_text và action_text.
- Câu không nêu bên vi phạm: bearer_text = null. KHÔNG suy đoán bên.
- Vi phạm chung ("vi phạm hợp đồng", "vi phạm bất kỳ điều khoản nào"): action_text là chính cụm đó.
- Câu danh từ hóa ("Phạt chậm tiến độ ...", "Chậm giao thiết bị bị phạt ...") vẫn là REMEDY; action_text là hành vi ("tiến độ", "giao thiết bị"), qualifier_text là "chậm".

Ví dụ 3 — "Nếu một bên vi phạm bất kỳ điều khoản nào dẫn đến việc chấm dứt Hợp đồng thì bên vi phạm sẽ phải chịu phạt vi phạm với mức 8% giá trị hợp đồng và bồi thường cho bên kia toàn bộ thiệt hại."
{"frames":[{"frame_type":"REMEDY","bearer_text":"một bên","action_text":"vi phạm bất kỳ điều khoản nào","qualifier_text":null,"condition_text":null,"consequence_text":"chịu phạt vi phạm với mức 8% giá trị hợp đồng"},{"frame_type":"REMEDY","bearer_text":"một bên","action_text":"vi phạm bất kỳ điều khoản nào","qualifier_text":null,"condition_text":null,"consequence_text":"bồi thường cho bên kia toàn bộ thiệt hại"}]}

Trả JSON: {"frames": [...]}""",
)
PROMPTS = {"v0": EXTRACT_SYSTEM_V0, "v1": EXTRACT_SYSTEM_V1, "v2": EXTRACT_SYSTEM_V2}


def _with_retry(call, attempts: int = 8):
    """Retry rate-limited provider calls (9Router relays GitHub 429 as 503)."""
    for i in range(attempts):
        try:
            return call()
        except Exception as exc:
            msg = str(exc)
            if i == attempts - 1 or not re.search(r"429|503|rate limit|timed out|timeout", msg, re.IGNORECASE):
                raise
            wait = re.search(r"reset after (?:(\d+)m\s*)?(\d+)s", msg)
            secs = int(wait.group(1) or 0) * 60 + int(wait.group(2)) if wait else 2 ** (i + 1)
            print(f"[rate limit] waiting {secs + 1}s (attempt {i + 1}/{attempts})", file=sys.stderr, flush=True)
            time.sleep(secs + 1)


def llm_extract(client, text: str, prompt: str = "v1") -> tuple[list[dict], int]:
    """Return frames with non-verbatim spans nulled, plus count of rejected spans."""
    data = _with_retry(lambda: client.complete_json(PROMPTS[prompt], f'Điều khoản: """{text}"""'))
    rejected, frames = 0, []
    for raw in data.get("frames") or []:
        spans = {}
        for k, v in raw.items():
            if k == "frame_type":
                continue
            if v and fold(v) not in fold(text):
                rejected += 1
                v = None
            spans[k] = v
        frames.extend(split_consequences({"frame_type": raw.get("frame_type"), "spans": spans}))
    return frames, rejected


def _best_match(gold: dict, predicted: list[dict]) -> dict:
    """Pair a gold frame with the predicted frame of the same type sharing most words.

    The LLM may split a clause into more frames than the gold set; index-based
    alignment would score the wrong frame.
    """
    def words(spans: dict) -> set[str]:
        return set(fold(" ".join(str(v) for v in spans.values() if v)).split())

    # held-out rows carry an anchor (verbatim fragment) instead of hand-cut spans
    target = words(gold["spans"]) if gold.get("spans") else set(fold(gold.get("anchor")).split())
    same_type = [f for f in predicted if f.get("frame_type") == gold["frame_type"]] or predicted
    if not same_type:
        return {"frame_type": gold["frame_type"], "spans": {}}
    return max(same_type, key=lambda f: len(target & words(f.get("spans") or {})))


# --------------------------------------------------------------------------- run

def run(mode: str, data_path: Path, comp_path: Path, lexicon_path: Path = LEXICON_PATH, prompt: str = "v1") -> dict:
    clauses = load_jsonl(data_path)
    lexicon = load_lexicon(lexicon_path)
    norm = Normalizer(lexicon)
    client = _client() if mode != "rules" else None
    chooser = make_chooser(client) if client else None

    span_errors = []
    rows = []  # one per gold frame
    extract_stats = Counter()
    for c in clauses:
        ctx = c.get("context") or {}
        predicted_frames = None
        if mode == "llm-full":
            predicted_frames, rej = llm_extract(client, c["text"], prompt)
            extract_stats["rejected_spans"] += rej
            extract_stats["frames_returned"] += len(predicted_frames)
        for i, gf in enumerate(c["frames"]):
            if "spans" not in gf and mode != "llm-full":
                raise SystemExit(f"{c['id']}: frames without spans can only be scored with --mode llm-full")
            for k, v in (gf.get("spans") or {}).items():
                if v and fold(v) not in fold(c["text"]):
                    span_errors.append(f"{c['id']}#{i}.{k}")
            if predicted_frames is not None:
                frame = _best_match(gf, predicted_frames)
            else:
                frame = gf
            res = norm.normalize(frame, c["text"], ctx, chooser, profile=c["profile"])
            spans = frame.get("spans") or {}
            cond_text = spans.get("condition_text")
            qual = spans.get("qualifier_text")
            if not cond_text and qual and _CONDITION_LIKE.search(fold(qual)):
                cond_text = qual  # threshold landed in the qualifier slot
            cond = parse_condition(cond_text)
            rows.append({
                "id": f"{c['id']}#{i}",
                "clause": c["id"],
                "profile": c["profile"],
                "frame_type": gf["frame_type"],
                "gold_key": tuple(gf["gold_key"]) if gf.get("gold_key") else None,
                "pred_key": res.key,
                "layer": res.layer,
                "gold_consequence": gf.get("gold_consequence"),
                "consequence": parse_consequence(spans.get("consequence_text")),
                "condition": cond,
                "condition_unparsed": bool(cond_text) and cond is None,
                "text": c["text"],
                "pred_spans": spans if predicted_frames is not None else None,
            })

    # key accuracy (UNMAPPED is correct when gold says no key)
    correct = [r for r in rows if r["pred_key"] == r["gold_key"]]
    mapped = [r for r in rows if r["pred_key"] is not None]
    mapped_correct = [r for r in mapped if r["pred_key"] == r["gold_key"]]
    wrong_mapped = [r for r in mapped if r["pred_key"] != r["gold_key"]]

    # pair grouping across the whole set
    pred_same = gold_same = both = 0
    false_merges = []
    for a, b in itertools.combinations(rows, 2):
        # a back-off key ("?") is never grouped with anything
        p = a["pred_key"] is not None and BACKOFF not in a["pred_key"] and a["pred_key"] == b["pred_key"]
        g = a["gold_key"] is not None and a["gold_key"] == b["gold_key"]
        pred_same += p
        gold_same += g
        both += p and g
        if p and not g:
            false_merges.append((a["id"], b["id"], a["pred_key"]))

    # consequence parse (REMEDY only)
    cons_rows = [r for r in rows if r["gold_consequence"]]
    cons_ok = [
        r for r in cons_rows
        if r["consequence"]["type"] == r["gold_consequence"]["type"]
        and r["consequence"]["value"] == r["gold_consequence"]["value"]
    ]

    # decision table: with gold keys (isolates the table) and end-to-end
    by_clause = {r["clause"]: r for r in rows}
    comps = load_jsonl(comp_path) if comp_path and comp_path.exists() else []
    dec_gold, dec_e2e = [], []
    for cp in comps:
        a, b = by_clause[cp["a"]], by_clause[cp["b"]]
        g = decide({**a, "key": a["gold_key"]}, {**b, "key": b["gold_key"]})
        e = decide({**a, "key": a["pred_key"]}, {**b, "key": b["pred_key"]})
        dec_gold.append({**cp, "got": g, "ok": g == cp["expected"]})
        dec_e2e.append({**cp, "got": e, "ok": e == cp["expected"]})

    def ci(k: int, n: int) -> dict:
        lo, hi = wilson(k, n)
        return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "wilson95": [round(lo, 3), round(hi, 3)]}

    return {
        "mode": mode,
        "lexicon": lexicon["version"],
        "prompt": prompt if mode == "llm-full" else None,
        "data": data_path.name,
        "n_clauses": len(clauses),
        "n_frames": len(rows),
        "gold_span_errors": span_errors,
        "extract": dict(extract_stats),
        "key_accuracy": ci(len(correct), len(rows)),
        "coverage_mapped": ci(len(mapped), len(rows)),
        "accuracy_when_mapped": ci(len(mapped_correct), len(mapped)),
        "layers": dict(sorted(Counter(r["layer"] for r in rows).items())),
        "layer_accuracy": {
            str(layer): ci(sum(r["pred_key"] == r["gold_key"] for r in rows if r["layer"] == layer),
                           sum(1 for r in rows if r["layer"] == layer))
            for layer in sorted({r["layer"] for r in rows})
        },
        "pair_precision": ci(both, pred_same),
        "pair_recall": ci(both, gold_same),
        "false_merges": [list(map(str, fm)) for fm in false_merges],
        "consequence_parse": ci(len(cons_ok), len(cons_rows)),
        "decision_gold_keys": ci(sum(d["ok"] for d in dec_gold), len(dec_gold)),
        "decision_end_to_end": ci(sum(d["ok"] for d in dec_e2e), len(dec_e2e)),
        "rows": [
            {k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()
             if k in ("id", "profile", "gold_key", "pred_key", "layer", "pred_spans")}
            for r in rows
        ],
        "wrong_keys": [
            {"id": r["id"], "gold": r["gold_key"], "pred": r["pred_key"], "layer": r["layer"]}
            for r in rows if r["pred_key"] != r["gold_key"]
        ],
        "wrong_mapped_ids": [r["id"] for r in wrong_mapped],
        "consequence_errors": [
            {"id": r["id"], "gold": r["gold_consequence"], "got": r["consequence"]}
            for r in cons_rows if r not in cons_ok
        ],
        "decisions": [
            {"pair": f"{d['a']}~{d['b']}", "expected": d["expected"], "gold_keys": d["got"], "e2e": e["got"]}
            for d, e in zip(dec_gold, dec_e2e)
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["rules", "llm-enum", "llm-full"], default="rules")
    ap.add_argument("--data", type=Path, default=HERE / "clauses_test.jsonl")
    ap.add_argument("--comparisons", type=Path, default=HERE / "comparisons_test.jsonl")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    ap.add_argument("--prompt", choices=["v0", "v1", "v2"], default="v1")
    args = ap.parse_args()

    result = run(args.mode, args.data, args.comparisons, args.lexicon, args.prompt)
    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.mode}-{result['lexicon']}-{args.data.stem.split('_')[-1]}"
    path = args.out / f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {k: result[k] for k in (
        "mode", "lexicon", "prompt", "data", "n_clauses", "n_frames", "gold_span_errors", "extract", "key_accuracy",
        "coverage_mapped", "accuracy_when_mapped", "layers", "layer_accuracy", "pair_precision",
        "pair_recall", "false_merges", "consequence_parse", "decision_gold_keys", "decision_end_to_end",
    )}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nfull result: {path}")


if __name__ == "__main__":
    main()
