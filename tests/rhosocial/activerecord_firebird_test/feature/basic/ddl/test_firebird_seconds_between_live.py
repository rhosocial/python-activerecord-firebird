# tests/rhosocial/activerecord_firebird_test/feature/basic/ddl/test_firebird_seconds_between_live.py
"""What only a running Firebird can say about ``seconds_between``.

The expression tests pin the rendered
``CAST(DATEDIFF(MILLISECOND ...) * 0.001 AS NUMERIC(18, 4))`` spelling and the
bind order. This file is the other half: that Firebird
accepts the spelling, keeps the sign, keeps the fraction and reads the value
back as seconds. It lives in the integration area rather than beside the
expression tests because the expression layer does no I/O.

Firebird timestamps carry four fractional digits -- tenths of a millisecond
-- and ``DATEDIFF(MILLISECOND, ...)`` returns ``NUMERIC(18, 1)``, so the
``0.0001`` second case asserts the finest resolution the engine stores rather
than a rounded whole second. ``DATEDIFF`` is signed, so the negative case
needs no ``CASE``.

The fixture skips when this machine has no Firebird client library, the same
way ``test_firebird_literal_defaults.py`` does; the server being reachable is
not enough for ``firebird-driver``.
"""

import datetime

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    QueryStatement,
    cast,
    seconds_between,
)
from rhosocial.activerecord.backend.expression.types import TimestampType
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend


@pytest.fixture
def live_backend(fb_config):
    backend = FirebirdBackend(connection_config=fb_config)
    try:
        backend.connect()
    except Exception as exc:  # noqa: BLE001 - the skip reason is the point
        pytest.skip(f"no reachable Firebird server: {exc}")
    yield backend
    try:
        backend.disconnect()
    except Exception:
        pass


def _scalar(backend, sql, params=()):
    """Run a one-row ``SELECT`` and return its only column as ``float``."""
    row = backend.execute(sql, params, fetch=True).data[0]
    return float(next(iter(row.values())))


class TestLiveSecondsBetween:
    """The spelling accepted, and the value it produces."""

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            (
                datetime.datetime(2026, 6, 4, 10, 0, 0),
                datetime.datetime(2026, 6, 4, 10, 0, 0),
                0.0,
            ),
            (
                datetime.datetime(2026, 6, 4, 10, 0, 0),
                datetime.datetime(2026, 6, 4, 11, 0, 0),
                3600.0,
            ),
            (
                datetime.datetime(2026, 6, 4, 11, 0, 0),
                datetime.datetime(2026, 6, 4, 10, 0, 0),
                -3600.0,
            ),
            (
                datetime.datetime(2026, 1, 31, 23, 59, 59),
                datetime.datetime(2026, 2, 1, 0, 0, 0),
                1.0,
            ),
            (
                datetime.datetime(2025, 12, 31, 12, 0, 0),
                datetime.datetime(2026, 1, 1, 12, 0, 0),
                86400.0,
            ),
            (
                datetime.datetime(2026, 6, 4, 10, 0, 0),
                datetime.datetime(2026, 6, 4, 10, 0, 0, 500_000),
                0.5,
            ),
            (
                datetime.datetime(2026, 6, 4, 10, 0, 0, 250_000),
                datetime.datetime(2026, 6, 4, 10, 0, 0),
                -0.25,
            ),
            (
                datetime.datetime(2026, 6, 4, 10, 0, 0, 100),
                datetime.datetime(2026, 6, 4, 10, 0, 0, 200),
                0.0001,
            ),
        ],
    )
    def test_elapsed(self, live_backend, start, end, expected):
        dialect = live_backend.dialect
        expr = seconds_between(
            dialect,
            cast(
                dialect,
                Literal(dialect, start, inline=True),
                TimestampType(dialect=dialect),
            ),
            cast(
                dialect,
                Literal(dialect, end, inline=True),
                TimestampType(dialect=dialect),
            ),
        ).as_("elapsed")
        query = QueryStatement(dialect, select=[expr], from_="RDB$DATABASE")
        sql, params = query.to_sql()
        assert _scalar(live_backend, sql, params) == pytest.approx(expected, abs=1e-9)

    def test_columns_in_a_row(self, live_backend):
        """The same question asked of two stored timestamps, not two binds."""
        table = "ar_fb_seconds_between"
        try:
            live_backend.execute(f"DROP TABLE {table}", fetch=False)
        except Exception:
            pass
        try:
            live_backend.execute(
                f"CREATE TABLE {table} ("
                f" id INT PRIMARY KEY,"
                f" started_at TIMESTAMP,"
                f" ended_at TIMESTAMP"
                f")",
                fetch=False,
            )
            live_backend.execute(
                f"INSERT INTO {table} (id, started_at, ended_at) VALUES"
                f" (1, TIMESTAMP '2026-03-01 00:00:00.0000',"
                f"     TIMESTAMP '2026-03-02 00:00:00.0000'),"
                f" (2, TIMESTAMP '2026-03-02 00:00:00.0000',"
                f"     TIMESTAMP '2026-03-01 00:00:00.0000'),"
                f" (3, TIMESTAMP '2026-03-01 00:00:00.7500',"
                f"     TIMESTAMP '2026-03-01 00:00:01.0000'),"
                f" (4, TIMESTAMP '2026-03-01 00:00:00.0001',"
                f"     TIMESTAMP '2026-03-01 00:00:00.0002')",
                fetch=False,
            )

            dialect = live_backend.dialect
            expr = seconds_between(
                dialect,
                Column(dialect, "started_at"),
                Column(dialect, "ended_at"),
            )
            expr_sql, params = expr.to_sql()
            rows = live_backend.execute(
                f"SELECT id, {expr_sql} FROM {table} ORDER BY id",
                params,
                fetch=True,
            ).data
            values = [float(row["id"]) for row in rows]
            assert values == [1, 2, 3, 4]

            elapsed = [float(list(row.values())[1]) for row in rows]
            assert elapsed[0] == pytest.approx(86400.0, abs=1e-9)
            assert elapsed[1] == pytest.approx(-86400.0, abs=1e-9)
            assert elapsed[2] == pytest.approx(0.25, abs=1e-9)
            assert elapsed[3] == pytest.approx(0.0001, abs=1e-9)
        finally:
            try:
                live_backend.execute(f"DROP TABLE {table}", fetch=False)
            except Exception:
                pass
