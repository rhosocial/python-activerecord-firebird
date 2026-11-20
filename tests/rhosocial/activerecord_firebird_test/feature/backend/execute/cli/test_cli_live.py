# tests/rhosocial/activerecord_firebird_test/feature/backend/execute/cli/test_cli_live.py
"""Live, end-to-end CLI tests for the Firebird backend.

The offline CLI suite (``feature/backend/construct/cli``) proves dispatch with
fakes. These tests drive ``main([...])`` against the *real* database owned by
this directory, through the real ``firebird-driver`` connection, and read the
JSON written to stdout. No MagicMock, no monkeypatched backend.

Only synchronous invocation is tested. Firebird's official driver offers no
async support, and the CLI rejects ``--async`` outright, so there is no async
half of these cases to mirror.

The fixture uses the backend-owned ``fb_config`` fixture. It skips only when
the server is unreachable; an available server never skips, so a failure here
is a real failure. Live execution therefore belongs to CI, where the Firebird
service is present.
"""

from __future__ import annotations

import json

import pytest

from rhosocial.activerecord.backend.impl.firebird.__main__ import main
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend

PROBE_TABLE = "AR_FB_LIVE_CLI_PROBE"


def _connection_argv(config):
    """Connection flags for the scenario's directory-owned database.

    Names and spellings follow
    ``rhosocial.activerecord.backend.impl.firebird.cli.connection``.
    ``fb_config`` carries the full physical file path (base path plus the
    logical database name derived from this test directory), so the CLI opens
    the same file the fixture did.
    """
    return [
        "--host",
        config.host or "localhost",
        "--port",
        str(config.port or 3050),
        "--database",
        config.database or "",
        "--user",
        config.username or "",
        "--password",
        config.password or "",
        "--charset",
        config.charset or "UTF8",
    ]


def _drop_probe_table(backend) -> None:
    """Drop the probe table, tolerating 'not there'.

    Matches the other connected suites in this tree: DDL goes through
    ``backend.execute`` and Firebird commits it itself. Calling
    ``commit_transaction()`` here fails with "No active transaction to commit"
    because there is no transaction left after a DDL statement.
    """
    try:
        backend.execute(f"DROP TABLE {PROBE_TABLE}", fetch=False)
    except Exception:
        pass


def _create_probe_table(backend) -> None:
    """Create a small user table so catalogue questions have a real answer.

    No explicit commit: Firebird auto-commits DDL, so the table is already
    visible to the CLI's separate connection. This is the same pattern the
    introspection live suites use for their probe objects.
    """
    _drop_probe_table(backend)
    backend.execute(
        f"CREATE TABLE {PROBE_TABLE} ("
        "id INTEGER NOT NULL PRIMARY KEY, label VARCHAR(64) NOT NULL)",
        fetch=False,
    )


@pytest.fixture
def live_cli_backend(fb_config):
    """A connected backend on the real database, with a probe table present.

    ``fb_config`` is the live fixture from the backend conftest: it resolves
    the first enabled scenario and the database owned by this directory. The
    only skip is for an unreachable server, matching the other connected
    suites in this tree.
    """
    backend = FirebirdBackend(connection_config=fb_config)
    try:
        backend.connect()
    except Exception as exc:
        pytest.skip(f"no reachable Firebird server: {exc}")
    try:
        backend.introspect_and_adapt()
        _create_probe_table(backend)
        yield backend
    finally:
        try:
            _drop_probe_table(backend)
        finally:
            try:
                backend.disconnect()
            except Exception:
                pass


def _normalized_names(rows):
    """Catalogue names come back upper-cased and may be CHAR-blank-padded."""
    return [str(row.get("name", "")).strip().upper() for row in rows]


class TestInfoLiveCli:
    """``info`` with no positional argument still reports the live connection."""

    def test_info_reports_live_database(self, live_cli_backend, capsys):
        main(["info", "-o", "json", *_connection_argv(live_cli_backend.config)])
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict)
        assert payload["database"]["type"] == "firebird"
        assert payload["database"]["connected"] is True
        assert payload["protocols"]
        assert "Firebird-specific" in payload["protocols"]


class TestQueryLiveCli:
    """``query`` executes SQL on the server, not on a stub result set."""

    def test_select_one_from_rdb_database(self, live_cli_backend, capsys):
        main(
            [
                "query",
                "SELECT 1 AS n FROM RDB$DATABASE",
                "-o",
                "json",
                *_connection_argv(live_cli_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and len(payload) == 1
        row = payload[0]
        key = next(k for k in row if k.upper() == "N")
        assert int(row[key]) == 1


class TestIntrospectLiveCli:
    """The safe catalogue families answer against a real Firebird database."""

    def test_tables_lists_the_probe_table(self, live_cli_backend, capsys):
        main(
            [
                "introspect",
                "tables",
                "-o",
                "json",
                *_connection_argv(live_cli_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert PROBE_TABLE in _normalized_names(payload)

    def test_columns_lists_the_probe_columns(self, live_cli_backend, capsys):
        main(
            [
                "introspect",
                "columns",
                PROBE_TABLE,
                "-o",
                "json",
                *_connection_argv(live_cli_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert {"ID", "LABEL"}.issubset(set(_normalized_names(payload)))

    def test_database_reports_database_facts(self, live_cli_backend, capsys):
        main(
            [
                "introspect",
                "database",
                "-o",
                "json",
                *_connection_argv(live_cli_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert isinstance(payload[0], dict) and payload[0]


class TestStatusLiveCli:
    """``status`` talks to the server status introspector over a live connection."""

    def test_all_reports_an_overview(self, live_cli_backend, capsys):
        main(
            [
                "status",
                "all",
                "-o",
                "json",
                *_connection_argv(live_cli_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict)
        assert payload["server_version"]
        assert isinstance(payload["configuration"], list)

    def test_config_lists_configuration_items(self, live_cli_backend, capsys):
        main(
            [
                "status",
                "config",
                "-o",
                "json",
                *_connection_argv(live_cli_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert all(row.get("name") for row in payload)
