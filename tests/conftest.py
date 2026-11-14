# tests/conftest.py
"""Root configuration for the Firebird backend's test tree.

The backend knows its own classes and how a scenario maps to a connection, so
no declaration table is needed here: the scenario is exposed as a parameterized
pytest fixture that the testsuite environment consumes.

Firebird connects to a database file, so the scenario carries the server and
the base file path; the logical database name is derived by the testsuite from
the test directory and injected by ``make_config(database)``.
"""

from pathlib import Path

import pytest
import support.firebird
from rhosocial.activerecord.testsuite.core.declarations import database_name

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

_SCENARIOS = [support.firebird.scenario(name) for name in support.firebird.SCENARIOS]


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Harden firebird-driver destructors against GC after connection close.

    firebird-driver 2.0.x Cursor.__del__ calls close() unconditionally when a
    statement is still attached; once the owning connection has been closed
    that close() aborts the process from inside the garbage collector, and
    under full-suite load it runs in a worker thread. Wrap the destructor so
    a failure to close during GC is swallowed instead of terminating pytest.
    """
    try:
        from firebird.driver.core import Cursor

        _orig_del = Cursor.__del__

        def _safe_del(self):
            # The original destructor calls close(), which releases the C
            # result set through interfaces.ResultSet.close() and aborts the
            # process when the owning connection is already closed
            # (firebird-driver 2.0.x). Only run the real destructor while the
            # connection is still alive; once the connection is gone, skip it
            # and let the OS reclaim the native resources at process exit.
            try:
                connection = getattr(self, "_connection", None)
                if connection is not None and not connection.is_closed():
                    _orig_del(self)
            except Exception:
                pass

        Cursor.__del__ = _safe_del
    except Exception:
        pass


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Mark known Firebird-incompatible tests as xfail.

    Only genuine, still-unresolved incompatibilities are marked here. Tests
    whose failures were fixed upstream (dialect capability gating, TIMESTAMP
    precision handling, NOT NULL -> IntegrityError mapping, identifier casing
    assertions) must NOT be xfailed: doing so would turn real passes into
    spurious XPASS entries.
    """
    for item in items:
        node_path = str(item.nodeid)
        # Recursive queries
        if "recursive_query" in node_path.lower():
            item.add_marker(
                pytest.mark.xfail(
                    reason="Firebird recursive CTE support needs dialect configuration",
                    strict=False,
                )
            )


@pytest.fixture(scope="session", params=_SCENARIOS, ids=lambda scenario: scenario.name)
def backend_scenario(request):
    """Return the scenario the tests run against; its id is the scenario name."""
    return request.param


def _first_scenario():
    """Return the first configured scenario (legacy fixtures need one)."""
    name = next(iter(support.firebird.SCENARIO_MAP), None)
    if name is None:
        raise RuntimeError("No Firebird scenario configured")
    return support.firebird.scenario(name)


@pytest.fixture
def dialect():
    """Create a FirebirdDialect with version 3.0."""
    d = FirebirdDialect()
    d.version = (3, 0, 0)
    return d


@pytest.fixture
def sqlite_style_dialect():
    """Create a FirebirdDialect with early version (FB 2.5 style)."""
    d = FirebirdDialect()
    d.version = (2, 5, 0)
    return d


@pytest.fixture
def fb4_dialect():
    """Create a FirebirdDialect with FB 4.0 features."""
    d = FirebirdDialect()
    d.version = (4, 0, 0)
    return d


@pytest.fixture
def fb_config(request):
    """Return a connection configuration for the *directory's* database.

    Firebird scenarios carry no database name: the logical name comes from the
    test directory, so sibling directories never share one file.  A missing
    file is created when the server is reachable; this fixture does not clear
    the database (only a directory contract's ``ensure_database`` does).
    """
    scenario = _first_scenario()
    database = database_name(Path(str(request.node.path)).parent)
    try:
        scenario.ensure_database(database)
    except Exception:
        # Keep the config shape even when the server is unreachable; the
        # backend's connect() reports the real failure to the test, and
        # live-server fixtures turn it into a skip.
        pass
    return scenario.make_config(database)


@pytest.fixture
def backend_config(fb_config):
    """Create a minimal backend configuration for testing."""
    return fb_config


@pytest.fixture
def backend(backend_config):
    """Create a FirebirdBackend instance (no connection)."""
    return FirebirdBackend(connection_config=backend_config)


@pytest.fixture
def fb_backend(fb_config):
    backend = FirebirdBackend(connection_config=fb_config)
    backend.connect()
    yield backend
    try:
        backend.disconnect()
    except Exception:
        pass


@pytest.fixture
def setup_test_table(fb_backend):
    table = "TEST_CRUD"
    try:
        fb_backend.execute(f"DROP TABLE {table}", fetch=False)
    except Exception:
        pass
    fb_backend.execute(f"""
        CREATE TABLE {table} (
            id INT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            amount DECIMAL(18,2) DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    yield table
    try:
        fb_backend.execute(f"DROP TABLE {table}", fetch=False)
    except Exception:
        pass
