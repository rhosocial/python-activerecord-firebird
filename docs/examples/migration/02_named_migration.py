# docs/examples/migration/02_named_migration.py
"""Class-style migration on the Firebird backend: MigrationRunner + CLI wiring.

Shows a synchronous NamedMigration whose up()/down() apply declarative model DDL
through ctx.apply(), so the expressions render via this backend's Firebird dialect.
The script runs the class programmatically with MigrationRunner and prints the
equivalent `named-migration` CLI invocation.

Requires a reachable Firebird database; with no database configured it prints setup
instructions and exits non-zero. See core's migration chapter for the migration
system itself and for the class-style dry-run caveat.
"""

import os
import sys
import tempfile
from typing import Optional

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig
from rhosocial.activerecord.backend.migration import (
    JSONFileMigrationRecordStore,
    MigrationContext,
    MigrationDirection,
    MigrationRunner,
    NamedMigration,
)
from rhosocial.activerecord.model import ActiveRecord

TABLE = "FB_MIGRATION_LOG_ENTRIES"

INSTRUCTIONS = """\
No Firebird database is configured. Set FIREBIRD_DATABASE (and the other
FIREBIRD_* variables) or provide tests/config/firebird_scenarios.yaml.
"""


class LogEntry(ActiveRecord):
    """Declarative model for the table created by the named migration."""

    __table_name__ = TABLE
    __primary_key__ = "id"

    id: Optional[int] = None
    message: str


class V001CreateLogEntries(NamedMigration):
    """Create (and drop) the Firebird log-entries table."""

    version = "v001_create_log_entries"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(LogEntry.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(LogEntry.drop_table_statement(if_exists=True, backend=ctx.backend))


def main() -> int:
    config = FirebirdConnectionConfig.from_env()
    if not config.database:
        print(INSTRUCTIONS, file=sys.stderr)
        return 2

    backend = FirebirdBackend(connection_config=config)
    try:
        backend.connect()
        backend.introspect_and_adapt()
    except Exception as exc:
        print(f"Could not connect to Firebird: {exc}", file=sys.stderr)
        print(INSTRUCTIONS, file=sys.stderr)
        return 2

    record_path = os.path.join(tempfile.gettempdir(), "firebird_named_migration_demo_records.json")
    fqn = f"{__name__}.V001CreateLogEntries"
    try:
        store = JSONFileMigrationRecordStore(record_path)
        runner = MigrationRunner(fqn)

        up = runner.run(backend, MigrationDirection.UP, record_store=store)
        print("== UP ==")
        print("  version:", up.version)
        print("  success:", up.success)
        print("  applied versions:", [r.version for r in store.get_applied()])

        down = runner.run(backend, MigrationDirection.DOWN, record_store=store)
        print("\n== DOWN ==")
        print("  version:", down.version)
        print("  success:", down.success)
        print("  applied versions after rollback:", [r.version for r in store.get_applied()])

        print("\nEquivalent CLI (put the class in an importable module such as myapp.migrations):")
        print("  python -m rhosocial.activerecord.backend.impl.firebird named-migration \\")
        print("      myapp.migrations.V001CreateLogEntries \\")
        print(f"      --database {config.database} --direction up --record-store ./records.json")
        return 0
    finally:
        backend.disconnect()
        if os.path.exists(record_path):
            os.remove(record_path)


if __name__ == "__main__":
    sys.exit(main())
