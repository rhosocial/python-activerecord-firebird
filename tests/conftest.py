# tests/conftest.py
"""Pytest configuration for Firebird backend tests."""

import os
import sys

import pytest

# Early-parse --scenarios from sys.argv and set FIREBIRD_ACTIVE_SCENARIOS env var.
# This must happen before providers.scenarios is imported (it filters its
# SCENARIO_MAP at import time).
_argv_scenarios = None
for _i, _arg in enumerate(sys.argv):
    if _arg.startswith("--scenarios="):
        _argv_scenarios = _arg.split("=", 1)[1]
    elif _arg == "--scenarios" and _i + 1 < len(sys.argv):
        _argv_scenarios = sys.argv[_i + 1]

if _argv_scenarios:
    os.environ["FIREBIRD_ACTIVE_SCENARIOS"] = _argv_scenarios

from rhosocial.activerecord.backend.impl.firebird import (
    FirebirdBackend,
    FirebirdConnectionConfig,
    FirebirdDialect,
)

os.environ.setdefault(
    "TESTSUITE_PROVIDER_REGISTRY",
    "providers.registry:provider_registry"
)


@pytest.hookimpl(trylast=True)
def pytest_addoption(parser):
    """Register the --scenarios option for selecting which scenarios to run."""
    parser.addoption(
        "--scenarios",
        action="store",
        default=None,
        help="Comma-separated list of scenario names to run "
             "(e.g., --scenarios=firebird_5,firebird_6).",
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Harden firebird-driver destructors against GC after connection close.

    firebird-driver 2.0.x Cursor.__del__ calls close() unconditionally when a
    statement is still attached; once the owning connection has been closed
    that close() aborts the process from inside the garbage collector, and
    under full-suite load it runs in a worker thread. Wrap the destructor so
    a failure to close during GC is swallowed instead of terminating pytest.
    """
    scenarios_opt = config.getoption("--scenarios", default=None)
    if scenarios_opt:
        os.environ["FIREBIRD_ACTIVE_SCENARIOS"] = scenarios_opt

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


def pytest_collection_modifyitems(items):
    """Mark known Firebird-incompatible tests as xfail.

    Only genuine, still-unresolved incompatibilities are marked here. Tests
    whose failures were fixed upstream (dialect capability gating, TIMESTAMP
    precision handling, NOT NULL -> IntegrityError mapping, identifier casing
    assertions) must NOT be xfailed: doing so would turn real passes into
    spurious XPASS entries.
    """
    for item in items:
        func_name = getattr(getattr(item, 'function', None), '__name__', '')
        node_path = str(item.nodeid)
        # Recursive queries
        if "recursive_query" in node_path.lower():
            item.add_marker(pytest.mark.xfail(
                reason="Firebird recursive CTE support needs dialect configuration",
                strict=False,
            ))


def _load_backend_config() -> FirebirdConnectionConfig:
    """Load backend config from scenario YAML, env vars, or fallback defaults."""
    config_path = os.getenv("FIREBIRD_SCENARIOS_CONFIG_PATH")
    if config_path and os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            scenarios = (data or {}).get("scenarios") or {}
            if scenarios:
                first = next(iter(scenarios.values()))
                return FirebirdConnectionConfig(**first)
        except Exception:
            pass
    try:
        return FirebirdConnectionConfig.from_env()
    except Exception:
        pass
    return FirebirdConnectionConfig(
        host="127.0.0.1",
        port=19583,
        database="/var/lib/firebird/data/test_db",
        username="root",
        password="password",
        charset="UTF8",
    )


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
def backend_config():
    """Create a minimal backend configuration for testing."""
    return _load_backend_config()


@pytest.fixture
def backend(backend_config):
    """Create a FirebirdBackend instance (no connection)."""
    return FirebirdBackend(connection_config=backend_config)