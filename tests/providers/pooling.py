# tests/providers/pooling.py
"""Database pooling helpers for the Firebird test providers.

Under parallel (pytest-xdist) runs with a positive pool size the providers
reuse a per-worker pooled database file instead of the shared scenario
``database`` file, so scenario variants of the same test can run concurrently
on different workers without conflicting.

Firebird's ``database`` is a file path, so the pool base name is the full
configured path and the pool name follows the same index-appending principle:
``{database}_{index}`` (the index is appended to the path), e.g.
``/var/lib/firebird/data/test_db`` -> ``/var/lib/firebird/data/test_db_0``.
Serial runs (no ``-n``) keep the previous behaviour: the provider connects to
the scenario's configured ``database``.

The scenario name selects the server (host/port); the pool index selects the
database file. The two are deliberately unrelated.
"""

import firebird.driver as fdb

from rhosocial.activerecord.testsuite.core.pool import (
    pooled_database_name,
    register_base_database,
    register_pool_reset_handler,
)

from .scenarios import SCENARIO_MAP, get_scenario_raw

# Derive each scenario's pooled-database base name from its configured
# ``database`` (the YAML ``database`` field, a file path). Registered at import
# time so any caller of pooled_database_name() / resolve_database_name()
# resolves names consistent with the scenario configuration.
for _scenario_name, _scenario_config in SCENARIO_MAP.items():
    register_base_database(_scenario_name, _scenario_config["database"])


def resolve_database_name(scenario_name: str):
    """
    Return the pooled database path (e.g. ``.../test_db_3``) used by a test for
    the given scenario, or ``None`` when pooling is inactive (callers then fall
    back to the scenario's configured database).
    """
    return pooled_database_name(scenario_name)


def _dsn(config, database: str) -> str:
    if config.host and config.port:
        return f"{config.host}/{config.port}:{database}"
    return database


def _connect(config, database: str):
    return fdb.connect(
        database=_dsn(config, database),
        user=config.username,
        password=config.password,
        charset=config.charset,
    )


def _reset_firebird_database(scenario_name: str, db_name: str) -> None:
    """Ensure the pooled database file exists and is empty on the scenario's server.

    Connects to the pooled ``db_name`` database, creating the file first when
    it is missing, and drops all leftover user tables/views so the test starts
    from a clean state. Errors are swallowed: a failed reset must not hide the
    underlying test failure.
    """
    if scenario_name not in SCENARIO_MAP:
        return
    _, config = get_scenario_raw(scenario_name)
    try:
        try:
            conn = _connect(config, db_name)
        except Exception:
            # First use: the pooled database file does not exist yet — create it.
            fdb.create_database(
                database=_dsn(config, db_name),
                user=config.username,
                password=config.password,
                charset=config.charset,
            )
            return
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT rc.RDB$RELATION_NAME, rc.RDB$CONSTRAINT_NAME "
                    "FROM RDB$RELATION_CONSTRAINTS rc "
                    "WHERE rc.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'"
                )
                for rel, cons in cursor.fetchall():
                    cursor.execute(
                        f'ALTER TABLE "{rel.rstrip()}" DROP CONSTRAINT "{cons.rstrip()}"'
                    )
                cursor.execute(
                    "SELECT RDB$RELATION_NAME, RDB$VIEW_BLR FROM RDB$RELATIONS "
                    "WHERE RDB$SYSTEM_FLAG = 0"
                )
                rows = cursor.fetchall()
                views = [name.rstrip() for name, blr in rows if blr is not None]
                tables = [name.rstrip() for name, blr in rows if blr is None]
                for view in views:
                    cursor.execute(f'DROP VIEW "{view}"')
                for table in tables:
                    cursor.execute(f'DROP TABLE "{table}"')
        finally:
            conn.close()
    except Exception as e:
        import traceback

        print(f"[FIREBIRD-POOL-PREP] failed for {scenario_name} {db_name}: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()


register_pool_reset_handler(_reset_firebird_database)
