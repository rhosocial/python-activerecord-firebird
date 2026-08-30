# src/rhosocial/activerecord/backend/impl/firebird/examples/named_connections/production.py
"""Production environment connection examples.

All configuration values can be overridden via environment variables:
    FIREBIRD_HOST, FIREBIRD_PORT, FIREBIRD_USER, FIREBIRD_PASSWORD, FIREBIRD_DATABASE
"""

import os

from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig


def _env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int_or_default(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def prod_db():
    """Production Firebird database connection.

    Reads connection parameters from environment variables with
    fallback to example.com documentation defaults.

    Returns:
        FirebirdConnectionConfig: Production database configuration.
    """
    return FirebirdConnectionConfig(
        host=_env_or_default("FIREBIRD_HOST", "prod-firebird.example.com"),
        port=_env_int_or_default("FIREBIRD_PORT", 3050),
        username=_env_or_default("FIREBIRD_USER", "app_user"),
        password=_env_or_default("FIREBIRD_PASSWORD", ""),
        database=_env_or_default("FIREBIRD_DATABASE", "production.fdb"),
        charset="UTF8",
        autocommit=True,
        wire_compression=True,
    )


def prod_db_ssl():
    """Production Firebird database with secure connection.

    Uses an SSL-capable connection for secure
    production connections.

    Returns:
        FirebirdConnectionConfig: Secure database configuration.
    """
    return FirebirdConnectionConfig(
        host=_env_or_default("FIREBIRD_HOST", "prod-firebird.example.com"),
        port=_env_int_or_default("FIREBIRD_PORT", 3050),
        username=_env_or_default("FIREBIRD_USER", "app_user"),
        password=_env_or_default("FIREBIRD_PASSWORD", ""),
        database=_env_or_default("FIREBIRD_DATABASE", "production.fdb"),
        charset="UTF8",
        autocommit=True,
        wire_compression=True,
    )


def prod_replica():
    """Production Firebird read replica connection.

    For read-heavy workloads, connect to a read replica
    to distribute load.

    Returns:
        FirebirdConnectionConfig: Read replica database configuration.
    """
    return FirebirdConnectionConfig(
        host=_env_or_default("FIREBIRD_REPLICA_HOST", "prod-firebird-replica.example.com"),
        port=_env_int_or_default("FIREBIRD_REPLICA_PORT", 3050),
        username=_env_or_default("FIREBIRD_REPLICA_USER", "app_user"),
        password=_env_or_default("FIREBIRD_REPLICA_PASSWORD", ""),
        database=_env_or_default("FIREBIRD_DATABASE", "production.fdb"),
        charset="UTF8",
        autocommit=True,
    )