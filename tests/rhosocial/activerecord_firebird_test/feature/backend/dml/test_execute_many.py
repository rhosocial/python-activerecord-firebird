# tests/rhosocial/activerecord_firebird_test/feature/backend/dml/test_execute_many.py
"""Synchronous Firebird backend ``execute_many`` batch semantics.

Verifies total affected-row accounting for a batch INSERT and the noop
behaviour for an empty parameter list against a real Firebird server,
mirroring the shared execute-many contract across backend repos.
"""

import pytest


@pytest.fixture
def batch_table(fb_backend):
    """Create (and later drop) a scratch table for batch inserts."""
    table = "TEST_EXECUTE_MANY"
    try:
        fb_backend.execute(f"DROP TABLE {table}", fetch=False)
    except Exception:
        pass
    fb_backend.execute(
        f"CREATE TABLE {table} (name VARCHAR(255) NOT NULL)",
        fetch=False,
    )
    yield table
    try:
        fb_backend.execute(f"DROP TABLE {table}", fetch=False)
    except Exception:
        pass


class TestExecuteMany:
    """Firebird ``execute_many`` batch behaviour."""

    def test_batch_insert_reports_total_affected_rows(self, fb_backend, batch_table):
        """Batch INSERT should report every affected row and persist them all."""
        sql = f"INSERT INTO {batch_table} (name) VALUES (?)"
        params_list = [(f"row_{i}",) for i in range(5)]
        result = fb_backend.execute_many(sql, params_list)
        assert result.affected_rows == 5, "batch insert should report all 5 affected rows"

        rows = fb_backend.execute(
            f"SELECT COUNT(*) FROM {batch_table}", fetch=True
        ).data
        count = rows[0]["count"] if rows else 0
        assert count == 5, "all 5 rows should be persisted"

    def test_empty_params_list_is_noop(self, fb_backend, batch_table):
        """An empty parameter list should insert nothing and not error."""
        result = fb_backend.execute_many(f"INSERT INTO {batch_table} (name) VALUES (?)", [])
        assert result is not None, "execute_many should return a QueryResult even for an empty batch"
        # Firebird's driver reports -1 for an empty executemany; treat any
        # non-positive count as "nothing inserted".
        assert result.affected_rows <= 0, "empty batch should affect no rows"

        rows = fb_backend.execute(
            f"SELECT COUNT(*) FROM {batch_table}", fetch=True
        ).data
        count = rows[0]["count"] if rows else 0
        assert count == 0, "no rows should exist after an empty batch"