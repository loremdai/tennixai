import importlib.util
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations" / "versions"


def _load_migration(revision: str = "0007"):
    migration_path = next(MIGRATIONS_DIR.glob(f"*_{revision}_*.py"))
    spec = importlib.util.spec_from_file_location(
        f"migration_{revision}", migration_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, count: int) -> None:
        self.count = count

    def scalar_one(self) -> int:
        return self.count


class _Connection:
    def __init__(self, null_marker_rows: int) -> None:
        self.null_marker_rows = null_marker_rows
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _Result(self.null_marker_rows)


def test_marker_migration_converts_legacy_api_values_to_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    operations: list[tuple[str, object]] = []
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: operations.append(("execute", str(statement))),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: operations.append(
            ("alter", (args, kwargs.get("nullable")))
        ),
    )

    migration.upgrade()

    assert [kind for kind, _ in operations] == ["alter", "alter", "alter", "execute", "execute", "execute"]
    assert all(payload[1] is True for _, payload in operations[:3])
    statements = [str(payload) for _, payload in operations[3:]]
    assert all("provider = 'api_tennis'" in statement for statement in statements)
    assert all("IS TRUE" not in statement for statement in statements)


def test_marker_migration_downgrade_refuses_to_coerce_unknown_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    connection = _Connection(null_marker_rows=1)
    altered: list[tuple[object, ...]] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: altered.append(args),
    )

    with pytest.raises(RuntimeError, match="unknown point markers"):
        migration.downgrade()

    assert connection.statements
    assert not altered


def test_marker_migration_can_downgrade_without_unknown_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    connection = _Connection(null_marker_rows=0)
    altered: list[tuple[object, ...]] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: altered.append(args),
    )

    migration.downgrade()

    assert len(altered) == 3


def test_freshness_migration_refuses_to_drop_persisted_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration("0008")
    connection = _Connection(null_marker_rows=1)
    dropped: list[tuple[object, ...]] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    monkeypatch.setattr(
        migration.op, "drop_column", lambda *args: dropped.append(args)
    )

    with pytest.raises(RuntimeError, match="persisted freshness data"):
        migration.downgrade()

    assert connection.statements
    assert not dropped


def test_freshness_migration_can_downgrade_when_column_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration("0008")
    connection = _Connection(null_marker_rows=0)
    dropped: list[tuple[object, ...]] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    monkeypatch.setattr(
        migration.op, "drop_column", lambda *args: dropped.append(args)
    )

    migration.downgrade()

    assert dropped == [("match_state_snapshots", "freshness")]
