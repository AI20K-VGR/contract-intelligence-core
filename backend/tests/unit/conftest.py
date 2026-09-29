"""Pytest fixtures for tests/unit/ — re-exports from conftest_contract.py.

Pytest only auto-loads files named exactly conftest.py, so we import the
contract fixtures here.
"""

from collections.abc import Iterator

import pytest
from tests.unit.conftest_contract import (  # noqa: F401
    contract_service,
    fake_repos,
    tmp_storage_dir,
)

from contract_intelligence.api import dossier_guard


@pytest.fixture(autouse=True)
def _allow_read_acl() -> Iterator[None]:
    """Router unit tests mock the service and have no database behind the ACL.

    The ``acl_*`` read dependencies need the dossier rows, so they are stubbed
    here; the ACL itself is covered by tests/unit/test_share_permissions.py and
    the M-07 suite (tests/integration/test_tenant_isolation.py).
    """
    from contract_intelligence.main import app

    stubs = [
        getattr(dossier_guard, name) for name in dossier_guard.__all__ if name.startswith("acl_")
    ]
    for dependency in stubs:
        app.dependency_overrides[dependency] = lambda: None
    yield
    for dependency in stubs:
        app.dependency_overrides.pop(dependency, None)


__all__ = ["contract_service", "fake_repos", "tmp_storage_dir"]
