"""Bounded context: extraction — kết quả trích xuất điều khoản, fact, citation.

Aggregate roots:

- ``Page`` — 1 trang vật lý của document
- ``OcrLine`` — 1 dòng OCR kèm bbox CPS
- ``Citation`` — quote + bbox, cốt lõi của BR-07
- ``ClauseNode`` — node trong cây Điều → Khoản → Điểm
- ``Fact`` — 1 thực thể trích xuất (tiền, ngày, bên…)
- ``PipelineRun`` — 1 lần chạy pipeline (checkpoint)

Context này **nhận** kết quả từ AI Service và lưu DB.
KHÔNG gọi OCR/AI trực tiếp — dùng ``ai_client`` Protocol để giao tiếp.
"""

from contract_intelligence.extraction.domain.entities.citation import Citation
from contract_intelligence.extraction.domain.entities.clause_node import ClauseNode, ClauseLevel
from contract_intelligence.extraction.domain.entities.fact import Fact, FactType
from contract_intelligence.extraction.domain.entities.ocr_line import OcrLine
from contract_intelligence.extraction.domain.entities.page import Page, PageKind
from contract_intelligence.extraction.domain.entities.pipeline_run import PipelineRun

__all__ = [
    "Citation",
    "ClauseLevel",
    "ClauseNode",
    "Fact",
    "FactType",
    "OcrLine",
    "Page",
    "PageKind",
    "PipelineRun",
]
