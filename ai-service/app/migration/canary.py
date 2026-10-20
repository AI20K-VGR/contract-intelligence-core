"""Small, deterministic primitives for migration canary cutover."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, MutableSequence
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, TypeAlias


class MigrationMode(str, Enum):
    """Traffic mode for the migration boundary."""

    LEGACY = "legacy"
    CANARY = "canary"
    CANONICAL = "canonical"


@dataclass(frozen=True, slots=True)
class MigrationConfig:
    mode: MigrationMode
    publish_verified_only: bool = True
    compare_enabled: bool = True


@dataclass(frozen=True, slots=True)
class SubmitRecord:
    run_id: str
    tenant_id: str
    dossier_id: str
    generation_id: str
    idempotency_key: str
    status: str
    source: str

    @property
    def digest(self) -> str:
        """Return a stable digest for the complete submission identity."""

        payload = {
            "run_id": self.run_id,
            "tenant_id": self.tenant_id,
            "dossier_id": self.dossier_id,
            "generation_id": self.generation_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "source": self.source,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


class DuplicateSubmissionConflict(ValueError):
    """Raised when an idempotency key is reused with a different digest."""


RecordStore: TypeAlias = (
    MutableMapping[str, SubmitRecord] | MutableSequence[SubmitRecord]
)


def _existing_record(records: RecordStore, idempotency_key: str) -> SubmitRecord | None:
    if isinstance(records, Mapping):
        candidate = records.get(idempotency_key)
        if isinstance(candidate, SubmitRecord):
            return candidate
        return next(
            (
                item
                for item in records.values()
                if isinstance(item, SubmitRecord)
                and item.idempotency_key == idempotency_key
            ),
            None,
        )

    return next(
        (item for item in records if item.idempotency_key == idempotency_key),
        None,
    )


def submit_once(records: RecordStore, record: SubmitRecord) -> SubmitRecord:
    """Insert a submission once, returning the durable record for retries."""

    existing = _existing_record(records, record.idempotency_key)
    if existing is not None:
        if existing.digest != record.digest:
            raise DuplicateSubmissionConflict(
                f"idempotency key conflict: {record.idempotency_key}"
            )
        return existing

    if isinstance(records, MutableMapping):
        records[record.idempotency_key] = record
    else:
        records.append(record)
    return record


def can_publish(record: SubmitRecord, current_generation: str) -> bool:
    """Allow only a verified record from the currently active generation."""

    return (
        record.generation_id == current_generation
        and isinstance(record.status, str)
        and record.status.casefold() == "verified"
    )


@dataclass(frozen=True, slots=True)
class OutputComparison:
    equal: bool
    differences: tuple[str, ...]

    @property
    def matched(self) -> bool:
        """Compatibility alias for callers that name parity as a match."""

        return self.equal


def _value_path(path: str, key: object) -> str:
    if isinstance(key, str) and key.isidentifier():
        return f"{path}.{key}"
    return f"{path}[{key!r}]"


def _diff_paths(legacy: Any, canonical: Any, path: str = "$") -> list[str]:
    if isinstance(legacy, Mapping) and isinstance(canonical, Mapping):
        differences: list[str] = []
        keys = sorted(
            set(legacy) | set(canonical),
            key=lambda key: (type(key).__name__, repr(key)),
        )
        for key in keys:
            child_path = _value_path(path, key)
            if key not in legacy or key not in canonical:
                differences.append(child_path)
            else:
                differences.extend(_diff_paths(legacy[key], canonical[key], child_path))
        return differences

    if isinstance(legacy, (list, tuple)) and isinstance(canonical, (list, tuple)):
        differences = []
        if type(legacy) is not type(canonical):
            differences.append(path)
            return differences
        common_length = min(len(legacy), len(canonical))
        for index in range(common_length):
            differences.extend(_diff_paths(legacy[index], canonical[index], f"{path}[{index}]"))
        differences.extend(
            f"{path}[{index}]"
            for index in range(common_length, max(len(legacy), len(canonical)))
        )
        return differences

    if type(legacy) is not type(canonical) or legacy != canonical:
        return [path]
    return []


def compare_outputs(legacy: Any, canonical: Any) -> OutputComparison:
    """Compare JSON-like outputs and return stable paths for every difference."""

    differences = tuple(_diff_paths(legacy, canonical))
    return OutputComparison(equal=not differences, differences=differences)


def rollback_mode(config: MigrationConfig) -> MigrationConfig:
    """Switch traffic to legacy while preserving the safety/audit flags."""

    return replace(config, mode=MigrationMode.LEGACY)
