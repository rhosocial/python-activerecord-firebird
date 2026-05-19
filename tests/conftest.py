# tests/conftest.py
"""Pytest configuration for Firebird backend tests."""

from typing import Optional

import pytest

from rhosocial.activerecord.backend.impl.firebird import (
    FirebirdBackend,
    FirebirdConnectionConfig,
    FirebirdDialect,
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
    return FirebirdConnectionConfig(
        host="localhost",
        port=3050,
        database="test.fdb",
        username="SYSDBA",
        password="masterkey",
        charset="UTF8",
    )


@pytest.fixture
def backend(backend_config):
    """Create a FirebirdBackend instance (no connection)."""
    return FirebirdBackend(connection_config=backend_config)