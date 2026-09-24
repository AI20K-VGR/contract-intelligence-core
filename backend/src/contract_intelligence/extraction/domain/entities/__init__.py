"""Entities — pure dataclass, không ORM."""

from contract_intelligence.extraction.domain.entities.citation import Citation
from contract_intelligence.extraction.domain.entities.clause_node import ClauseLevel, ClauseNode
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
