# src/rhosocial/activerecord/backend/impl/firebird/examples/named_connections/development.py
"""Development environment connection examples.

All configuration values can be overridden via environment variables:
    FIREBIRD_HOST, FIREBIRD_PORT, FIREBIRD_USER, FIREBIRD_PASSWORD, FIREBIRD_DATABASE
"""

import os

from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig


def _env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int_or_default(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def local_dev():
    """Local development Firebird database connection.

    Reads connection parameters from environment variables with
    fallback to localhost defaults.

    Returns:
        FirebirdConnectionConfig: Development database configuration.
    """
    return FirebirdConnectionConfig(
        host=_env_or_default("FIREBIRD_HOST", "localhost"),
        port=_env_int_or_default("FIREBIRD_PORT", 3050),
        username=_env_or_default("FIREBIRD_USER", "SYSDBA"),
        password=_env_or_default("FIREBIRD_PASSWORD", "masterkey"),
        database=_env_or_default("FIREBIRD_DATABASE", "dev.fdb"),
        charset="UTF8",
        autocommit=True,
    )


def local_dev_no_auth():
    """Local Firebird connection without authentication.

    Reads connection parameters from environment variables with
    fallback to localhost defaults.

    Returns:
        FirebirdConnectionConfig: No-auth database configuration.
    """
    return FirebirdConnectionConfig(
        host=_env_or_default("FIREBIRD_HOST", "localhost"),
        port=_env_int_or_default("FIREBIRD_PORT", 3050),
        username=_env_or_default("FIREBIRD_USER", "SYSDBA"),
        password=_env_or_default("FIREBIRD_PASSWORD", "masterkey"),
        database=_env_or_default("FIREBIRD_DATABASE", "dev.fdb"),
        charset="UTF8",
        autocommit=True,
    )


def test_db():
    """Test database connection.

    Reads connection parameters from environment variables with
    fallback to localhost defaults.

    Returns:
        FirebirdConnectionConfig: Test database configuration.
    """
    return FirebirdConnectionConfig(
        host=_env_or_default("FIREBIRD_HOST", "localhost"),
        port=_env_int_or_default("FIREBIRD_PORT", 3050),
        username=_env_or_default("FIREBIRD_USER", "SYSDBA"),
        password=_env_or_default("FIREBIRD_PASSWORD", "masterkey"),
        database=_env_or_default("FIREBIRD_DATABASE", "test.fdb"),
        charset="UTF8",
        autocommit=True,
    )