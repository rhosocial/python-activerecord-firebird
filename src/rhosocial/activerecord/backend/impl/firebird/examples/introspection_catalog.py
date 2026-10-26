# src/rhosocial/activerecord/backend/impl/firebird/examples/introspection_catalog.py
"""Every introspection question this backend can ask, rendered and executed.

The expression layer is the contract: a catalogue question is a statement
object, the dialect owns the SQL, and the introspector only builds, executes
and parses. This example exercises that contract without the introspector --
it constructs each statement itself, renders it through the dialect, and runs
it against a live server. A family whose statement renders but does not
execute is a defect the expression layer owns, and this script fails on it.

Two things are deliberately *not* done here:

* nothing is created, altered or dropped, so the script leaves the database
  exactly as it found it;
* nothing is invented. A family with no object to describe prints
  ``skipped`` and says why, rather than querying a made-up name.

Run it against the server the test suite uses (the same variables the CLI
reads):

    FIREBIRD_HOST=db-dev-1-n.rho.im FIREBIRD_PORT=19582 \
    FIREBIRD_DATABASE=/var/lib/firebird/data/test_db \
    FIREBIRD_USER=SYSDBA FIREBIRD_PASSWORD=password \
    python introspection_catalog.py

Add ``--sql`` to print each statement before running it, and ``--only <family>``
to run one family.

With no reachable server the script prints these instructions and exits
non-zero; it does not report a catalogue it could not read.
"""

import argparse
import os
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

from firebird.driver import connect

from rhosocial.activerecord.backend.expression.introspection import (
    ColumnInfoQueryStatement,
    DatabaseInfoQueryStatement,
    ForeignKeyQueryStatement,
    IndexInfoQueryStatement,
    TableInfoQueryStatement,
    TableListQueryStatement,
    TriggerInfoQueryStatement,
    TriggerListQueryStatement,
    ViewInfoQueryStatement,
    ViewListQueryStatement,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.introspection import (
    FirebirdCharsetListQueryStatement,
    FirebirdCollationListQueryStatement,
    FirebirdConstraintListQueryStatement,
    FirebirdDependencyQueryStatement,
    FirebirdDomainInfoQueryStatement,
    FirebirdDomainListQueryStatement,
    FirebirdExceptionInfoQueryStatement,
    FirebirdExceptionListQueryStatement,
    FirebirdFunctionArgumentQueryStatement,
    FirebirdFunctionListQueryStatement,
    FirebirdGeneratorListQueryStatement,
    FirebirdGeneratorValueQueryStatement,
    FirebirdPrivilegeQueryStatement,
    FirebirdProcedureListQueryStatement,
    FirebirdProcedureParameterQueryStatement,
    FirebirdPublicationListQueryStatement,
    FirebirdRoleListQueryStatement,
    FirebirdViewRelationQueryStatement,
)

USAGE = __doc__


def build_dialect() -> FirebirdDialect:
    """A dialect bound to the server version we are about to talk to."""
    for factory in (
        lambda: FirebirdDialect(version=(5, 0, 4)),
        lambda: FirebirdDialect((5, 0, 4)),
        FirebirdDialect,
    ):
        try:
            return factory()
        except TypeError:
            continue
    raise RuntimeError("cannot construct FirebirdDialect")


def connect_from_env():
    host = os.environ.get("FIREBIRD_HOST")
    database = os.environ.get("FIREBIRD_DATABASE")
    if not host or not database:
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    dsn = f"{host}/{os.environ.get('FIREBIRD_PORT', '3050')}:{database}"
    return connect(
        dsn,
        user=os.environ.get("FIREBIRD_USER", "SYSDBA"),
        password=os.environ.get("FIREBIRD_PASSWORD", ""),
        charset=os.environ.get("FIREBIRD_CHARSET", "UTF8"),
    )


def fetch(cur, statement) -> List[Dict[str, Any]]:
    """Render a statement through the dialect, run it, return named rows."""
    sql, params = statement.to_sql()
    cursor = cur.execute(sql, params or ())
    names = [d[0] for d in (cursor.description or ())]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def discover(cur) -> Dict[str, Optional[str]]:
    """Find one object per family to describe, without assuming which exist."""

    def first(sql: str) -> Optional[str]:
        row = cur.execute(sql).fetchone()
        return row[0].strip() if row and row[0] is not None else None

    found: Dict[str, Optional[str]] = {}
    found["table"] = first(
        "select rdb$relation_name from rdb$relations "
        "where coalesce(rdb$system_flag, 0) = 0 and rdb$view_blr is null "
        "order by rdb$relation_name rows 1"
    )
    found["fk_table"] = first(
        "select rdb$relation_name from rdb$relation_constraints "
        "where rdb$constraint_type = 'FOREIGN KEY' rows 1"
    )
    found["view"] = first(
        "select rdb$relation_name from rdb$relations "
        "where coalesce(rdb$system_flag, 0) = 0 and rdb$view_blr is not null "
        "order by rdb$relation_name rows 1"
    )
    found["trigger"] = first(
        "select rdb$trigger_name from rdb$triggers "
        "where coalesce(rdb$system_flag, 0) = 0 rows 1"
    )
    found["procedure"] = (
        first(
            "select rdb$procedure_name from rdb$procedures "
            "where coalesce(rdb$system_flag, 0) = 0 rows 1"
        )
        or first("select rdb$procedure_name from rdb$procedures rows 1")
    )
    found["function"] = (
        first(
            "select rdb$function_name from rdb$functions "
            "where coalesce(rdb$system_flag, 0) = 0 rows 1"
        )
        or first("select rdb$function_name from rdb$functions rows 1")
    )
    found["domain"] = first(
        "select rdb$field_name from rdb$fields "
        "where coalesce(rdb$system_flag, 0) = 0 and rdb$field_name not starting with 'RDB$' "
        "rows 1"
    )
    found["generator"] = first(
        "select rdb$generator_name from rdb$generators rows 1"
    )
    found["exception"] = first(
        "select rdb$exception_name from rdb$exceptions rows 1"
    )
    return found


def build_cases(
    dialect: FirebirdDialect, names: Dict[str, Optional[str]]
) -> List[Tuple[str, Callable[[], Any], str]]:
    """(family, statement factory, note) for every question the layer offers.

    The note says which scope the family reads: the whole database, one
    relation, or one named object. ``skip`` in place of a factory means the
    database has no object of that family to describe.
    """
    table = names.get("table")
    fk_table = names.get("fk_table")
    view = names.get("view")
    trigger = names.get("trigger")
    procedure = names.get("procedure")
    function = names.get("function")
    domain = names.get("domain")
    generator = names.get("generator")
    exception = names.get("exception")

    cases: List[Tuple[str, Any, str]] = [
        # --- core families: every backend answers these -------------------
        ("database", lambda: DatabaseInfoQueryStatement(dialect), "whole database"),
        ("tables", lambda: TableListQueryStatement(dialect), "whole database"),
        (
            "views",
            lambda: ViewListQueryStatement(dialect),
            "whole database",
        ),
        (
            "triggers",
            lambda: TriggerListQueryStatement(dialect),
            "whole database",
        ),
        # --- Firebird's own schema objects --------------------------------
        (
            "generators",
            lambda: FirebirdGeneratorListQueryStatement(dialect, include_system=True),
            "whole database, system included",
        ),
        ("domains", lambda: FirebirdDomainListQueryStatement(dialect), "whole database"),
        (
            "exceptions",
            lambda: FirebirdExceptionListQueryStatement(dialect, include_system=True),
            "whole database, system included",
        ),
        (
            "procedures",
            lambda: FirebirdProcedureListQueryStatement(dialect, include_system=True),
            "whole database, system included",
        ),
        (
            "functions",
            lambda: FirebirdFunctionListQueryStatement(dialect, include_system=True),
            "whole database, system included",
        ),
        (
            "constraints",
            lambda: FirebirdConstraintListQueryStatement(dialect, include_system=True),
            "whole database, system included",
        ),
        (
            "roles",
            lambda: FirebirdRoleListQueryStatement(dialect, include_system=True),
            "whole database, system included",
        ),
        ("privileges", lambda: FirebirdPrivilegeQueryStatement(dialect), "whole database"),
        ("charsets", lambda: FirebirdCharsetListQueryStatement(dialect), "whole database"),
        (
            "collations",
            lambda: FirebirdCollationListQueryStatement(dialect),
            "whole database",
        ),
        (
            "dependencies",
            lambda: FirebirdDependencyQueryStatement(dialect),
            "whole database",
        ),
        (
            "view-relations",
            lambda: FirebirdViewRelationQueryStatement(dialect),
            "whole database",
        ),
        (
            "publications",
            lambda: FirebirdPublicationListQueryStatement(dialect, include_system=True),
            "whole database, system included (Firebird 4+)",
        ),
        # --- one relation --------------------------------------------------
        (
            "columns",
            (
                lambda: ColumnInfoQueryStatement(dialect, table)
                if table
                else None
            ),
            f"table {table}" if table else "no user table in this database",
        ),
        (
            "indexes",
            (
                lambda: IndexInfoQueryStatement(dialect, table)
                if table
                else None
            ),
            f"table {table}" if table else "no user table in this database",
        ),
        (
            "table-info",
            (
                lambda: TableInfoQueryStatement(dialect, table)
                if table
                else None
            ),
            f"table {table}" if table else "no user table in this database",
        ),
        (
            "constraints(one table)",
            (
                lambda: FirebirdConstraintListQueryStatement(dialect, table_name=table)
                if table
                else None
            ),
            f"table {table}" if table else "no user table in this database",
        ),
        (
            "privileges(one object)",
            (
                lambda: FirebirdPrivilegeQueryStatement(dialect, object_name=table)
                if table
                else None
            ),
            f"object {table}" if table else "no user table in this database",
        ),
        (
            "dependencies(one object)",
            (
                lambda: FirebirdDependencyQueryStatement(dialect, object_name=table)
                if table
                else None
            ),
            f"object {table}" if table else "no user table in this database",
        ),
        (
            "foreign-keys",
            (
                lambda: ForeignKeyQueryStatement(dialect, fk_table)
                if fk_table
                else None
            ),
            f"table {fk_table}" if fk_table else "no foreign key in this database",
        ),
        (
            "view-relations(one view)",
            (
                lambda: FirebirdViewRelationQueryStatement(dialect, view_name=view)
                if view
                else None
            ),
            f"view {view}" if view else "no view in this database",
        ),
        # --- one named object ----------------------------------------------
        (
            "view-info",
            (lambda: ViewInfoQueryStatement(dialect, view) if view else None),
            f"view {view}" if view else "no view in this database",
        ),
        (
            "trigger-info",
            (
                lambda: TriggerInfoQueryStatement(dialect, trigger)
                if trigger
                else None
            ),
            f"trigger {trigger}" if trigger else "no trigger in this database",
        ),
        (
            "generator-value",
            (
                lambda: FirebirdGeneratorValueQueryStatement(dialect, generator)
                if generator
                else None
            ),
            f"generator {generator}" if generator else "no generator in this database",
        ),
        (
            "domain-info",
            (lambda: FirebirdDomainInfoQueryStatement(dialect, domain) if domain else None),
            f"domain {domain}" if domain else "no domain in this database",
        ),
        (
            "exception-info",
            (
                lambda: FirebirdExceptionInfoQueryStatement(dialect, exception)
                if exception
                else None
            ),
            f"exception {exception}" if exception else "no exception in this database",
        ),
        (
            "procedure-parameters",
            (
                lambda: FirebirdProcedureParameterQueryStatement(dialect, procedure)
                if procedure
                else None
            ),
            f"procedure {procedure}" if procedure else "no procedure in this database",
        ),
        (
            "function-arguments",
            (
                lambda: FirebirdFunctionArgumentQueryStatement(dialect, function)
                if function
                else None
            ),
            f"function {function}" if function else "no function in this database",
        ),
        (
            "collations(one charset)",
            lambda: FirebirdCollationListQueryStatement(dialect, charset_name="UTF8"),
            "charset UTF8",
        ),
    ]
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sql", action="store_true", help="print each statement")
    parser.add_argument("--only", help="run one family only")
    parser.add_argument("--rows", type=int, default=3, help="sample rows to print")
    args = parser.parse_args()

    dialect = build_dialect()
    con = connect_from_env()
    cur = con.cursor()

    names = discover(cur)
    cases = build_cases(dialect, names)

    width = max(len(name) for name, _, _ in cases)
    failures = 0
    ran = 0

    print(f"server {con.server_version if hasattr(con, 'server_version') else '?'}"
          f"  objects: {', '.join(f'{k}={v}' for k, v in names.items() if v)}")
    print()
    print(f"{'family'.ljust(width)}  {'rows':>6}  {'params':>6}  scope")
    print(f"{'-' * width}  {'-' * 6}  {'-' * 6}  {'-' * 40}")

    for family, factory, note in cases:
        if args.only and family != args.only:
            continue
        if factory is None:
            print(f"{family.ljust(width)}  {'skip':>6}  {'':>6}  {note}")
            continue

        try:
            statement = factory()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"{family.ljust(width)}  {'FAIL':>6}  {'':>6}  {note}")
            print(f"    cannot build statement: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        if statement is None:
            print(f"{family.ljust(width)}  {'skip':>6}  {'':>6}  {note}")
            continue
        try:
            sql, params = statement.to_sql()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"{family.ljust(width)}  {'FAIL':>6}  {'':>6}  {note}")
            print(f"    cannot render: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        if args.sql:
            print(f"-- {family}: {sql}")
            print(f"--   params={params}")
        try:
            rows = fetch(cur, statement)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"{family.ljust(width)}  {'FAIL':>6}  {len(params or ()):>6}  {note}")
            print(f"    {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
            print(f"    sql: {sql}")
            traceback.print_exc(limit=1)
            continue

        ran += 1
        print(f"{family.ljust(width)}  {len(rows):>6}  {len(params or ()):>6}  {note}")
        for row in rows[: max(args.rows, 0)]:
            fields = ", ".join(
                f"{k}={str(v).strip()[:28]!r}" for k, v in list(row.items())[:5] if v is not None
            )
            print(f"    {fields}")

    cur.close()
    con.close()

    print()
    print(f"{ran} statement(s) executed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

