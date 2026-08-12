# src/rhosocial/activerecord/backend/impl/firebird/examples/connection/quickstart.py
"""Quickstart example for Firebird backend."""

from rhosocial.activerecord.backend.impl.firebird import (
    FirebirdBackend,
    FirebirdConnectionConfig,
)


def main():
    """Quickstart example showing basic usage."""
    config = FirebirdConnectionConfig(
        host="localhost",
        port=3050,
        database="/firebird/data/test.fdb",
        username="SYSDBA",
        password="masterkey",
        charset="UTF8",
    )

    backend = FirebirdBackend(connection_config=config)

    try:
        backend.connect()

        version = backend.get_server_version()
        print(f"Connected to Firebird {'.'.join(str(v) for v in version)}")

        result = backend.execute("SELECT 1 FROM RDB$DATABASE", fetch=True)
        print(f"Result: {result.data}")

    finally:
        backend.disconnect()


if __name__ == "__main__":
    main()