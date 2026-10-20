"""Benchmark the production OCR engine: quality, performance and cost.

Runs `mistral_verified` (the engine the Kafka job uses, configured from the same
AI1_* environment variables -- e.g. AI1_COST_MODE=budget) over every sample in a
manifest and scores it against hand-corrected ground truth:

- Quality: CER, WER (raw and whitespace-normalized), diacritic error rate, and
  Critical Field Accuracy per field type, per page, per document.
- Performance: wall time per document, per-page latency percentiles, model
  call counts and mean call latency.
- Cost: Mistral pages x AI1_*_PRICE_PER_PAGE_USD, GPT from the real token usage
  of the run.

Only pages that went through OCR are scored; pages read from the PDF's own text
layer (PyMuPDF) cost nothing and are left out unless `--include-native`.

THIS CALLS PAID APIs (Mistral, OpenAI) for every scanned page. Run it where the
worker runs (API keys in the environment), e.g. inside the ai1-worker container:

    python scripts/benchmark_ocr_production.py --manifest data/manifest.csv \\
        --out reports/benchmark
    # rebuild the Markdown report from a saved run, no API calls:
    python scripts/benchmark_ocr_production.py --report-only reports/benchmark/results.json

Manifest columns used: sample_id, file_path, ground_truth_text (pages separated
by \\f, see scripts/ground_truth_review.py), ground_truth_critical_fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


# -- running ---------------------------------------------------------------------


def run(manifest: Path, out_dir: Path, workers: int, include_native: bool) -> Path:
    import contract_ocr.infrastructure.ocr.openai_vision_ocr as openai_module
    from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
    from contract_ocr.application.use_cases.process_document import ProcessDocument
    from contract_ocr.domain.entities import CriticalField, Experiment
    from contract_ocr.infrastructure.backend_ocr_job import _get_engine
    from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
    from contract_ocr.infrastructure.image.renderer import PdfRenderer
    from contract_ocr.infrastructure.metrics.ocr_metrics import OCRMetrics, critical_accuracy
    from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

    lock = threading.Lock()
    current = {"doc": None}
    calls: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "seconds": 0.0})
    doc_calls: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    gpt = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0}

    original_cost = openai_module._cost_details

    def record_cost(model: str, usage: dict | None, *args: Any) -> Any:
        result = original_cost(model, usage, *args)
        with lock:
            gpt["requests"] += 1
            gpt["input_tokens"] += (usage or {}).get("input", 0)
            gpt["output_tokens"] += (usage or {}).get("output", 0)
            gpt["usd"] += (result or {}).get("total", 0.0)
        return result

    openai_module._cost_details = record_cost

    def count(obj: Any, method: str, label: str) -> None:
        original = getattr(obj, method)

        def timed(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                with lock:
                    calls[label]["calls"] += 1
                    calls[label]["seconds"] += time.perf_counter() - start
                    doc_calls[current["doc"]][label] += 1

        setattr(obj, method, timed)

    engine = _get_engine("mistral")
    count(engine.text_reader, "recognize_page", "mistral text reader")
    count(engine.verifier, "recognize_page", "mistral verifier")
    count(engine.fallback_reader, "recognize_page", "gpt full-page fallback")
    count(engine.arbiter, "read_regions", "gpt crops (arbiter)")
    count(engine.arbiter, "recognize_page", "gpt full-page (arbiter)")

    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    metrics = OCRMetrics()
    base = manifest.parent.parent if manifest.parent.name == "data" else manifest.parent
    with manifest.open(encoding="utf-8") as stream:
        samples = list(csv.DictReader(stream))

    documents = []
    started = time.perf_counter()
    for sample in samples:
        sid = sample["sample_id"]
        current["doc"] = sid
        t0 = time.perf_counter()
        document = processor.execute(
            str(base / sample["file_path"]), sid, Experiment(id="BENCH", engine="mistral"),
            engine, out_dir / "raw" / sid, "BENCH", 150, max_workers=workers,
        )
        wall = time.perf_counter() - t0
        gt_pages = (base / sample["ground_truth_text"]).read_text(encoding="utf-8").split("\f")
        fields = [
            CriticalField.model_validate(f)
            for f in json.loads((base / sample["ground_truth_critical_fields"]).read_text(encoding="utf-8"))
        ]
        pages = []
        for page in document.pages:
            route = str(page.input_type)
            if route == "TEXT_LAYER" and not include_native:
                continue
            n = page.page_number
            hyp = "\n".join(line.text for line in page.lines)
            ref = gt_pages[n - 1] if n <= len(gt_pages) else ""
            raw, norm = metrics.text(ref, hyp), metrics.text(_norm(ref), _norm(hyp))
            by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
            missed = []
            for f in (f for f in fields if f.page == n):
                ok = critical_accuracy([f], hyp)["critical_field_correct"]
                by_type[f.type][0] += ok
                by_type[f.type][1] += 1
                if not ok:
                    missed.append(f.raw_text)
            pages.append({
                "page": n, "route": route, "ms": round(page.processing_ms, 1),
                "ref_chars": len(ref), "ref_words": len(ref.split()),
                "ref_chars_norm": len(_norm(ref)), "ref_words_norm": len(_norm(ref).split()),
                "cer": raw["cer"], "wer": raw["wer"],
                "cer_norm": norm["cer"], "wer_norm": norm["wer"],
                "diacritic_errors": raw["diacritic_errors"],
                "diacritic_aligned": raw["diacritic_aligned_letters"],
                "crit_by_type": dict(by_type), "crit_missed": missed,
                "review_flags": sum(w.startswith("needs_review") for w in page.warnings),
            })
        documents.append({"sample_id": sid, "wall_s": round(wall, 2), "pages": pages,
                          "calls": dict(doc_calls[sid])})
        print(f"done {sid} {wall:.1f}s", flush=True)

    results = {
        "config": {k: v for k, v in os.environ.items() if k.startswith("AI1_") and "KEY" not in k},
        "total_wall_s": round(time.perf_counter() - started, 2),
        "calls": {k: dict(v) for k, v in calls.items()},
        "gpt": gpt,
        "documents": [d for d in documents if d["pages"]],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "results.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _norm(text: str) -> str:
    return " ".join(text.split())


# -- reporting (no API calls) ------------------------------------------------------


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.2f}%"


def aggregate(pages: list[dict]) -> dict[str, Any]:
    """Micro-averaged over pages, weighted by ground-truth length."""
    def weighted(metric: str, weight: str) -> float:
        total = sum(p[weight] for p in pages)
        return sum(p[metric] * p[weight] for p in pages) / total if total else 0.0

    aligned = sum(p["diacritic_aligned"] for p in pages)
    ok = sum(v[0] for p in pages for v in p["crit_by_type"].values())
    total = sum(v[1] for p in pages for v in p["crit_by_type"].values())
    return {
        "pages": len(pages),
        "cer": weighted("cer", "ref_chars"), "wer": weighted("wer", "ref_words"),
        "cer_norm": weighted("cer_norm", "ref_chars_norm"),
        "wer_norm": weighted("wer_norm", "ref_words_norm"),
        "diacritic": sum(p["diacritic_errors"] for p in pages) / aligned if aligned else None,
        "crit_ok": ok, "crit_total": total, "crit": ok / total if total else None,
        "review": sum(p["review_flags"] for p in pages),
    }


def cost(results: dict) -> dict[str, float]:
    config = results.get("config", {})
    text_price = float(config.get("AI1_TEXT_PRICE_PER_PAGE_USD") or 0.002)
    verifier_price = float(config.get("AI1_VERIFIER_PRICE_PER_PAGE_USD") or 0.004)
    calls = results["calls"]
    text_pages = calls.get("mistral text reader", {}).get("calls", 0)
    verifier_pages = calls.get("mistral verifier", {}).get("calls", 0)
    pages = sum(len(d["pages"]) for d in results["documents"])
    total = text_pages * text_price + verifier_pages * verifier_price + results["gpt"]["usd"]
    return {
        "text_pages": text_pages, "text_usd": text_pages * text_price, "text_price": text_price,
        "verifier_pages": verifier_pages, "verifier_usd": verifier_pages * verifier_price,
        "verifier_price": verifier_price, "gpt_usd": results["gpt"]["usd"], "total_usd": total,
        "per_page": total / pages if pages else 0.0,
    }


def report(results: dict) -> str:
    docs = results["documents"]
    pages = [p for d in docs for p in d["pages"]]
    overall, spend = aggregate(pages), cost(results)
    mode = results.get("config", {}).get("AI1_COST_MODE", "accuracy")
    lines = [
        "# Benchmark OCR production", "",
        f"Engine `mistral_verified`, AI1_COST_MODE=`{mode}`. {len(docs)} tài liệu, "
        f"{overall['pages']} trang qua OCR.", "",
        "## Chất lượng", "",
        "| CER | WER | CER chuẩn hoá | WER chuẩn hoá | Lỗi dấu | Critical Field Accuracy | Cờ review |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {_pct(overall['cer'])} | {_pct(overall['wer'])} | {_pct(overall['cer_norm'])} | "
        f"{_pct(overall['wer_norm'])} | {_pct(overall['diacritic'])} | {_pct(overall['crit'])} "
        f"({overall['crit_ok']}/{overall['crit_total']}) | {overall['review']} |", "",
        "| Tài liệu | Trang | CER chuẩn hoá | WER chuẩn hoá | Critical Field | Thời gian |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for d in docs:
        a = aggregate(d["pages"])
        lines.append(f"| {d['sample_id']} | {a['pages']} | {_pct(a['cer_norm'])} | {_pct(a['wer_norm'])} | "
                     f"{_pct(a['crit'])} ({a['crit_ok']}/{a['crit_total']}) | {d['wall_s']:.1f} s |")
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for p in pages:
        for kind, (ok, total) in p["crit_by_type"].items():
            by_type[kind][0] += ok
            by_type[kind][1] += total
    lines += ["", "| Loại field | Đúng / Tổng | Accuracy |", "|---|---:|---:|"]
    lines += [f"| {k} | {ok}/{t} | {_pct(ok / t if t else None)} |" for k, (ok, t) in sorted(by_type.items())]
    missed = [f"- {d['sample_id']} tr.{p['page']}: `{m}`" for d in docs for p in d["pages"] for m in p["crit_missed"]]
    if missed:
        lines += ["", "Field sai/thiếu:", "", *missed]
    ms = sorted(p["ms"] for p in pages)
    lines += ["", "## Hiệu năng", "", "| Chỉ số | Giá trị |", "|---|---:|",
              f"| Tổng thời gian | {results['total_wall_s']:.1f} s |",
              f"| Thông lượng | {len(pages) / results['total_wall_s'] * 60:.1f} trang/phút |"]
    if ms:
        lines.append(f"| Mỗi trang — trung vị / p95 / max | {statistics.median(ms) / 1000:.1f} / "
                     f"{ms[min(len(ms) - 1, round(0.95 * (len(ms) - 1)))] / 1000:.1f} / {ms[-1] / 1000:.1f} s |")
    lines += ["", "| Model | Lời gọi | Trung bình / lời gọi |", "|---|---:|---:|"]
    lines += [f"| {k} | {int(v['calls'])} | {v['seconds'] / v['calls']:.1f} s |"
              for k, v in sorted(results["calls"].items()) if v["calls"]]
    g = results["gpt"]
    lines += ["", "## Chi phí", "", "| Hạng mục | Số lượng | Thành tiền |", "|---|---:|---:|",
              f"| Mistral đọc chữ | {spend['text_pages']} trang × ${spend['text_price']} | ${spend['text_usd']:.4f} |",
              f"| Mistral đối chiếu | {spend['verifier_pages']} trang × ${spend['verifier_price']} | ${spend['verifier_usd']:.4f} |",
              f"| GPT | {g['requests']} request · {g['input_tokens']:,} in / {g['output_tokens']:,} out token | ${spend['gpt_usd']:.4f} |",
              f"| **Tổng** | {len(pages)} trang | **${spend['total_usd']:.4f}** |", "",
              f"**${spend['per_page'] * 1000:.2f} / 1.000 trang** (${spend['per_page']:.4f}/trang)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "manifest.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "benchmark")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("AI1_MAX_PAGES_IN_FLIGHT", "8")))
    parser.add_argument("--include-native", action="store_true")
    parser.add_argument("--report-only", type=Path, help="results.json of an earlier run; no API calls")
    args = parser.parse_args()
    path = args.report_only or run(args.manifest, args.out, args.workers, args.include_native)
    results = json.loads(path.read_text(encoding="utf-8"))
    out = path.with_name("report.md")
    out.write_text(report(results), encoding="utf-8")
    print(f"report: {out}")


if __name__ == "__main__":
    main()
