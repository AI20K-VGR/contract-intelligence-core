from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_history_has_one_unambiguous_head() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
