"""Catch SQL batches that offline Alembic accepts but asyncpg cannot prepare."""

import importlib.util
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
import sqlparse
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"


@pytest.mark.parametrize("path", sorted(MIGRATIONS.glob("*.py")), ids=lambda path: path.stem)
@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_each_execute_contains_one_postgres_statement(
    path: Path, direction: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    original_execute = Operations.execute

    def checked_execute(self: Operations, sql: Any, **kwargs: Any) -> None:
        statements = sqlparse.split(str(sql))
        assert len(statements) == 1, (
            f"{path.name} {direction} sends {len(statements)} commands to asyncpg: {sql}"
        )
        original_execute(self, sql, **kwargs)

    monkeypatch.setattr(Operations, "execute", checked_execute)
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": StringIO()}
    )
    with Operations.context(context):
        getattr(migration, direction)()
