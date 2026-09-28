"""Bounded context: contract lifecycle.

Aggregate roots:

- ``Dossier`` — 1 hợp đồng + 0..n phụ lục (xem ``DOC-04b`` §3)
- ``Document`` — 1 file PDF thuộc dossier (role = ``contract`` | ``annex``)
- ``Job`` — 1 lần xử lý dossier qua pipeline

Trách nhiệm context: upload, lưu file vào MinIO, state machine job.
KHÔNG làm: OCR, trích xuất, xung đột (của các bounded context khác).
"""

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus

__all__ = ["Dossier", "Document", "DocumentRole", "Job", "JobStatus"]
