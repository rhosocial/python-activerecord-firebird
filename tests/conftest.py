# tests/conftest.py
"""Pytest configuration for Firebird backend tests."""

import os
from typing import Optional

import pytest

from rhosocial.activerecord.backend.impl.firebird import (
    FirebirdBackend,
    FirebirdConnectionConfig,
    FirebirdDialect,
)

os.environ.setdefault(
    "TESTSUITE_PROVIDER_REGISTRY",
    "tests.providers.registry:provider_registry"
)


def pytest_collection_modifyitems(items):
    """Mark async tests as xfail since Firebird backend doesn't support async."""
    for item in items:
        node_path = str(item.nodeid)
        if "Async" in node_path or "async" in node_path:
            item.add_marker(pytest.mark.xfail(
                reason="Firebird backend does not support async operations",
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