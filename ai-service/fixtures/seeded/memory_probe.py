"""Peak memory of one offline AI2 run on a large fictional dossier (no LLM).

    python -m fixtures.seeded.memory_probe --pages 200    # prints peak RSS and per-stage tracemalloc peaks

Linux only for RSS (reads /proc/self/status VmHWM). The dossier repeats invented clauses
so node, pair and frame counts grow with the page count the way a long contract does.
"""

from __future__ import annotations

import argparse
import os
import time
import tracemalloc
from unittest import mock

from fixtures.seeded import common
from fixtures.seeded import funnel as seeded_funnel
from fixtures.seeded.common import DISCLAIMER, build_request, context_caps_env

_CLAUSES = (
    "Bên B giao {n} bộ thiết bị loại {k} tại kho của Bên A trong vòng {d} ngày kể từ ngày ký Hợp đồng.",
    "Bên A thanh toán {p}% giá trị đợt {k} trong vòng {d} ngày kể từ ngày nhận được hóa đơn hợp lệ.",
    "Bên B bảo hành thiết bị loại {k} trong thời hạn {m} tháng kể từ ngày ký biên bản nghiệm thu.",
    "Bên B chậm giao hàng đợt {k} thì chịu phạt {r}% giá trị phần chậm giao cho mỗi ngày chậm.",
    "Hai bên nghiệm thu khối lượng đợt {k} trong vòng {d} ngày làm việc kể từ ngày Bên B thông báo.",
    "Việc thay đổi địa điểm giao hàng đợt {k} phải được Bên A thông báo trước ít nhất {d} ngày.",
)


def _pages(count: int, articles: int) -> list[list[str]]:
    pages, article = [], 0
    for page in range(count):
        lines = ["HỢP ĐỒNG KIỂM THỬ BỘ NHỚ - TÀI LIỆU HƯ CẤU"] + (DISCLAIMER if page == 0 else [])
        for _ in range(articles):
            article += 1
            lines.append(f"Điều {article}. Nội dung thực hiện đợt {article}")
            for index, template in enumerate(_CLAUSES, start=1):
                lines.append(f"{article}.{index}. " + template.format(
                    n=10 + article % 40, k=article, d=5 + article % 25, p=10 + article % 50,
                    m=12 + article % 24, r=round(0.1 + (article % 5) / 10, 1)))
        lines.append(f"Trang {page + 1}")
        pages.append(lines)
    return pages


def _lines(words: bool):
    """``common._lines`` with every line inside the page and, optionally, word boxes."""
    def build(doc: str, page_no: int, texts: list[str]) -> list[dict]:
        height = 0.9 / max(len(texts), 1)
        lines = []
        for index, text in enumerate(texts, start=1):
            line_id = f"{doc}:s1:p{page_no:03d}:l{index:03d}"
            y0 = 0.05 + (index - 1) * height
            box = [0.1, y0, 0.9, y0 + height * 0.8]
            line = {"line_id": line_id, "raw_text": text, "bbox": box, "bbox_source": "native",
                    "geometry_status": "measured", "words": []}
            if words:
                tokens, start = text.split(" "), 0
                step = 0.8 / max(len(tokens), 1)
                for number, token in enumerate(tokens):
                    if token:
                        line["words"].append({
                            "word_id": f"{line_id}:w{number:03d}", "text": token,
                            "char_start": start, "char_end": start + len(token),
                            "bbox": [0.1 + number * step, box[1], 0.1 + (number + 1) * step, box[3]],
                            "bbox_source": "native", "geometry_status": "measured", "engine_confidence": 0.99,
                        })
                    start += len(token) + 1
            lines.append(line)
        return lines
    return build


def _vm_hwm_mb() -> float | None:
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=200)
    parser.add_argument("--articles-per-page", type=int, default=8)
    parser.add_argument("--words", action="store_true", help="add per-word boxes like a real OCR snapshot")
    args = parser.parse_args()
    os.environ.setdefault("AI2_SEMANTIC_CONTEXT_CAPS", context_caps_env())
    with mock.patch.object(common, "_lines", _lines(args.words)):
        payload = build_request(dossier_id="dossier-memory-probe", body_pages=_pages(args.pages, args.articles_per_page),
                            annex_pages=[["PHỤ LỤC 01", *DISCLAIMER, "1. Sửa đổi khoản 2 Điều 1 như sau: Bên A thanh "
                                          "toán 20% giá trị đợt 1 trong vòng 10 ngày kể từ ngày nhận được hóa đơn hợp lệ."]])
    peaks: dict[str, float] = {}

    def staged(name, real):
        def wrapper(*a, **kw):
            tracemalloc.reset_peak()
            started = time.perf_counter()
            try:
                return real(*a, **kw)
            finally:
                peaks[name] = round(tracemalloc.get_traced_memory()[1] / 2**20, 1)
                peaks[name + "_s"] = round(time.perf_counter() - started, 1)
        return wrapper

    from app.pipeline import idp
    from app.pipeline.contract_graph import pair_builder
    tracemalloc.start()
    started = time.perf_counter()
    with (mock.patch.object(idp, "build_semantic_extension", staged("semantic", idp.build_semantic_extension)),
          mock.patch.object(pair_builder, "generate_pair_candidates",
                            staged("pair_candidates", pair_builder.generate_pair_candidates))):
        funnel = seeded_funnel.run(payload)
    total_peak = tracemalloc.get_traced_memory()[1] / 2**20
    print(f"pages {args.pages} nodes {len(funnel.texts)} candidates {len(funnel.candidates)} "
          f"seconds {time.perf_counter() - started:.1f}")
    print(f"python_peak_mb {total_peak:.1f} rss_peak_mb {_vm_hwm_mb()} stages {peaks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
