"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_dossier_id() -> str:
    return "dos_01HZ1234567890ABCDEFGHIJ"


@pytest.fixture
def sample_document_id() -> str:
    return "doc_01HZ1234567890ABCDEFGHIJ"
