"""JSON Schema loading and validation for the canonical AI1/AI2 boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin

from app.contracts.errors import ContractValidationError


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = REPO_ROOT / "docs" / "contracts"


def load_contract_schema(filename: str) -> dict[str, Any]:
    path = CONTRACT_ROOT / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"cannot load contract schema {filename}: {exc}") from exc


def validate_contract(instance: Mapping[str, Any], filename: str, *, error_code: str) -> None:
    """Validate a payload against a repository-owned JSON Schema.

    ``jsonschema`` is deliberately loaded here rather than at module import so
    compat-only code can still be inspected when optional runtime dependencies
    are not installed. Official handoff execution always requires the package.
    """

    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover - dependency installation failure
        raise ContractValidationError(
            "jsonschema is required for canonical contract validation"
        ) from exc

    schema = load_contract_schema(filename)
    registry = Registry()
    for candidate in CONTRACT_ROOT.glob("*.schema.json"):
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(loaded, dict):
            resource = Resource.from_contents(loaded)
            registry = registry.with_resource(candidate.name, resource)
            if loaded.get("$id"):
                schema_id = str(loaded["$id"])
                registry = registry.with_resource(schema_id, resource)
                registry = registry.with_resource(
                    urljoin(str(schema.get("$id") or ""), candidate.name), resource
                )

    validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    error = errors[0]
    path = ".".join(str(part) for part in error.absolute_path) or "$"
    raise ContractValidationError(f"{path}: {error.message}", code=error_code)
