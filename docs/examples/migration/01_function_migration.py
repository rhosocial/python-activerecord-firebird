# docs/examples/migration/01_function_migration.py
"""Function-style migration on the Firebird backend: dry-run -> UP -> DOWN.

Uses this repository's FirebirdConnectionConfig / FirebirdBackend together with the
core function-style migration API. Requires a reachable Firebird database; with no
database configured the script prints setup instructions and exits non-zero.

Run from the repository root, for example:

    $env:FIREBIRD_DATABASE='localhost/3050:/var/lib/firebird/data/test.fdb'
    $env:FIREBIRD_USERNAME='SYSDBA'
    $env:FIREBIRD_PASSWORD='masterkey'
    .venv3.14\\Scripts\\python.exe docs\\examples\\migration\\01_function_migration.py

The migration system itself is documented in core's migration chapter; this script
only demonstrates this backend's configuration and synchronous wiring.
"""

import os
import sys
import tempfile
from typing import Optional

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig
from rhosocial.activerecord.backend.migration import (
    MigrationDirection,
    migration,
    run_migration_group,
)
from rhosocial.activerecord.backend.migration.record import JSONFileMigrationRecordStore
from rhosocial.activerecord.model import ActiveRecord

TABLE = "FB_MIGRATION_WIDGETS"

INSTRUCTIONS = """\
No Firebird database is configured. Set FIREBIRD_DATABASE (and the other
FIREBIRD_* variables) or provide tests/config/firebird_scenarios.yaml.
"""


class Widget(ActiveRecord):
    """Declarative model whose DDL the migration renders through this dialect."""

    __table_name__ = TABLE
    __primary_key__ = "id"

    id: Optional[int] = None
    name: str


@migration("v001_create_widgets", description="create the Firebird widgets table")
def create_widgets(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(Widget.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(Widget.drop_table_statement(if_exists=True, backend=ctx.backend))


def main() -> int:
    config = FirebirdConnectionConfig.from_env()
    if not config.database:
        print(INSTRUCTIONS, file=sys.stderr)
        return 2

    backend = FirebirdBackend(connection_config=config)
    try:
        backend.connect()
        backend.introspect_and_adapt()  # version gates need the adapted dialect
    except Exception as exc:
        print(f"Could not connect to Firebird: {exc}", file=sys.stderr)
        print(INSTRUCTIONS, file=sys.stderr)
        return 2

    record_path = os.path.join(tempfile.gettempdir(), "firebird_migration_demo_records.json")
    fqn = f"{__name__}:create_widgets"
    try:
        # 1) dry run: renders through the Firebird dialect, writes nothing.
        preview = run_migration_group(backend, [fqn], dry_run=True)
        print("== dry run ==")
        print("  statements:", preview.dry_run_total)
        for label, sql, params in preview.dry_run_sql:
            print(f"  [{label}] {sql}")
        print("  records written:", preview.records_written)

        # 2) real UP: applies the DDL and writes one version record.
        store = JSONFileMigrationRecordStore(record_path)
        up = run_migration_group(backend, [fqn], record_store=store)
        print("\n== UP ==")
        print("  applied:", up.applied)
        print("  versions:", up.versions)
        print("  applied versions:", [r.version for r in store.get_applied()])

        # 3) DOWN: rolls the DDL back and clears the applied version.
        down = run_migration_group(
            backend, [fqn], direction=MigrationDirection.DOWN, record_store=store
        )
        print("\n== DOWN ==")
        print("  rolled back:", down.rolled_back)
        print("  applied versions after rollback:", [r.version for r in store.get_applied()])
        return 0
    finally:
        backend.disconnect()
        if os.path.exists(record_path):
            os.remove(record_path)


if __name__ == "__main__":
    sys.exit(main())
