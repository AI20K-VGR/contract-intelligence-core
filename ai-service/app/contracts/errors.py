from __future__ import annotations


class DossierDeletedError(ValueError):
    """A permanently deleted dossier cannot be processed or written again."""


class ContractValidationError(ValueError):
    """Low-level validation error shared by the canonical contract boundary."""

    def __init__(self, message: str, *, code: str = "CONTRACT_SCHEMA_INVALID") -> None:
        super().__init__(message)
        self.code = code
