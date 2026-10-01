"""Unit tests cho domain layer — không có DB, không có framework.

Các test này verify domain logic thuần túy:
- Entity invariants
- State machine transitions
- Domain exceptions
"""

import pytest

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.shared.exceptions import InvalidStateTransition


class TestDossierEntity:
    def test_new_dossier_has_ulid_prefix(self, sample_dossier_id: str) -> None:
        dossier = Dossier(name="Hợp đồng A")
        assert dossier.id.startswith("dos_")
        assert dossier.has_conflicts is False

    def test_dossier_state_machine_uploaded_can_transition_to_processing(self) -> None:
        dossier = Dossier(name="Test")
        job = Job(dossier_id=dossier.id, status=JobStatus.UPLOADED)
        dossier.jobs.append(job)
        # No exception
        dossier.ensure_can_transition_to(JobStatus.PROCESSING)

    def test_dossier_state_machine_cannot_jump_from_uploaded_to_approved(self) -> None:
        dossier = Dossier(name="Test")
        job = Job(dossier_id=dossier.id, status=JobStatus.UPLOADED)
        dossier.jobs.append(job)
        with pytest.raises(InvalidStateTransition):
            dossier.ensure_can_transition_to(JobStatus.APPROVED)


class TestDocumentEntity:
    def test_new_document_default_role_is_contract(self) -> None:
        doc = Document(dossier_id="dos_1", filename="contract.pdf")
        assert doc.role == DocumentRole.CONTRACT

    def test_document_equality_by_id(self) -> None:
        doc1 = Document(id="doc_abc", dossier_id="dos_1", filename="a.pdf")
        doc2 = Document(id="doc_abc", dossier_id="dos_1", filename="a.pdf")
        doc3 = Document(id="doc_xyz", dossier_id="dos_1", filename="a.pdf")
        assert doc1 == doc2
        assert doc1 != doc3


class TestJobEntity:
    def test_new_job_default_status_is_uploaded(self) -> None:
        job = Job(dossier_id="dos_1")
        assert job.status == JobStatus.UPLOADED

    def test_job_id_has_job_prefix(self) -> None:
        job = Job(dossier_id="dos_1")
        assert job.id.startswith("job_")
