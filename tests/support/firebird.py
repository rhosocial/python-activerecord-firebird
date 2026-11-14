# tests/support/firebird.py
"""The Firebird backend's test scenarios.

Firebird connects to a database *file*, so a scenario is a server plus the
scenario's own database file (the path the CI image creates).  The scenario
file holds server and file parameters only; the logical database name comes
from the test directory and is appended to the scenario's base path here:

    /var/lib/firebird/data/test_db + _test_basic_crud
        -> /var/lib/firebird/data/test_db_test_basic_crud

The base path itself is the scenario-level connection (maintenance work, CLI
black-box checks), because Firebird cannot drop the file it is connected to
and the CI image has already created that one.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import firebird.driver as fdb
import yaml

from rhosocial.activerecord.backend.impl.firebird.backend import (
    AsyncFirebirdBackend,
    FirebirdBackend,
)
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

CONFIG_PATH = Path(
    os.environ.get("FIREBIRD_SCENARIOS_CONFIG_PATH")
    or Path(__file__).resolve().parents[1] / "config" / "firebird_scenarios.yaml"
)

# The base database path is a file parameter, not a connection database name:
# the logical name is derived from the test directory.  ``enabled`` is a
# scenario toggle, not a connection parameter.
FILE_ONLY_KEYS = ("database", "enabled")


def _load_scenarios(path: Path = CONFIG_PATH) -> Dict[str, Dict[str, Any]]:
    """Load one server-parameter dict per scenario from the YAML file."""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    entries = data.get("scenarios")
    if not entries:
        raise ValueError(f"{path} defines no scenarios")
    return {
        name: {key: value for key, value in entry.items() if key not in FILE_ONLY_KEYS}
        for name, entry in entries.items()
    }


def _load_base_paths(path: Path = CONFIG_PATH) -> Dict[str, str]:
    """Return the scenario's base database file per scenario name."""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    entries = data.get("scenarios") or {}
    base_paths = {}
    for name, entry in entries.items():
        base_path = entry.get("database") or os.environ.get("FIREBIRD_DATABASE")
        if not base_path:
            raise ValueError(
                f"{path} scenario {name!r} defines no database file; "
                "set its 'database' key or FIREBIRD_DATABASE"
            )
        base_paths[name] = str(base_path)
    return base_paths


SCENARIO_MAP = _load_scenarios()
_BASE_PATHS = _load_base_paths()
SCENARIOS = tuple(SCENARIO_MAP)


def _identifier(name: str) -> str:
    """Quote a Firebird identifier (object names come from the catalogue)."""
    return '"' + name.replace('"', '""') + '"'


@dataclass(frozen=True)
class FirebirdScenario:
    """One Firebird test scenario: a server, a base file and the backend classes."""

    name: str
    server: Dict[str, Any]
    base_path: str
    backend_class: Any = FirebirdBackend
    async_backend_class: Any = AsyncFirebirdBackend

    def database_path(self, database: str) -> str:
        """Return the physical database file for this logical database name."""
        return f"{self.base_path}_{database}"

    def make_config(self, database: str) -> FirebirdConnectionConfig:
        """Return the connection configuration for this logical database."""
        return FirebirdConnectionConfig(**self.server, database=self.database_path(database))

    def make_raw_config(self) -> FirebirdConnectionConfig:
        """Return the scenario-level configuration (its base database file)."""
        return FirebirdConnectionConfig(**self.server, database=self.base_path)

    def ensure_database(self, database: str) -> None:
        """Create this logical database's file when it does not exist yet."""
        path = self.database_path(database)
        try:
            self._connect(path).close()
        except Exception:
            # First use: the file is absent (or unreadable) -- create it.
            self._create(path)

    def reset_database(self, database: str) -> None:
        """Ensure this logical database exists and is empty.

        Firebird cannot drop the file through the connection that uses it, so
        the reset clears every user view and table (dropping their foreign
        keys first) instead of recreating the file.  A missing file is created
        first; a failed reset is raised, never swallowed, so the directory's
        first test reports the real problem.
        """
        path = self.database_path(database)
        try:
            connection = self._connect(path)
        except Exception:
            self._create(path)
            return
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT rc.RDB$RELATION_NAME, rc.RDB$CONSTRAINT_NAME "
                "FROM RDB$RELATION_CONSTRAINTS rc "
                "WHERE rc.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'"
            )
            for relation, constraint in cursor.fetchall():
                cursor.execute(
                    f"ALTER TABLE {_identifier(relation.rstrip())} "
                    f"DROP CONSTRAINT {_identifier(constraint.rstrip())}"
                )
            cursor.execute(
                "SELECT RDB$RELATION_NAME, RDB$VIEW_BLR FROM RDB$RELATIONS "
                "WHERE RDB$SYSTEM_FLAG = 0"
            )
            rows = cursor.fetchall()
            views = [name.rstrip() for name, blr in rows if blr is not None]
            tables = [name.rstrip() for name, blr in rows if blr is None]
            for view in views:
                cursor.execute(f"DROP VIEW {_identifier(view)}")
            for table in tables:
                cursor.execute(f"DROP TABLE {_identifier(table)}")
            # ``with connection:`` rolls the transaction back on this driver,
            # so the drops would vanish without this explicit commit.
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # --- server-level plumbing -------------------------------------------

    def _dsn(self, path: str) -> str:
        host = self.server.get("host")
        port = self.server.get("port")
        if host and port:
            return f"{host}/{port}:{path}"
        return path

    def _connect(self, path: str):
        return fdb.connect(
            database=self._dsn(path),
            user=self.server.get("username"),
            password=self.server.get("password"),
            charset=self.server.get("charset", "UTF8"),
        )

    def _create(self, path: str) -> None:
        fdb.create_database(
            database=self._dsn(path),
            user=self.server.get("username"),
            password=self.server.get("password"),
            charset=self.server.get("charset", "UTF8"),
        )


def scenario(name: str) -> FirebirdScenario:
    """Return the scenario called ``name``."""
    try:
        server = SCENARIO_MAP[name]
        base_path = _BASE_PATHS[name]
    except KeyError:
        raise KeyError(f"Unknown Firebird scenario: {name}") from None
    return FirebirdScenario(name, dict(server), base_path)


def get_enabled_scenarios():
    """Return the scenarios this backend enables, as a name -> server map."""
    return {name: dict(server) for name, server in SCENARIO_MAP.items()}


def get_scenario(name: str):
    """Return ``(backend_class, config)`` for a benchmark database."""
    current = scenario(name)
    current.reset_database("test_benchmark")
    return current.backend_class, current.make_config("test_benchmark")


def get_scenario_raw(name: str):
    """Return ``(backend_class, config)`` for a scenario-level connection.

    Falls back to the first configured scenario when CI enables only one.  The
    config points at the scenario's base database file, not a test directory's
    logical database.
    """
    resolved = name if name in SCENARIO_MAP else next(iter(SCENARIO_MAP), None)
    if resolved is None:
        raise KeyError("No %s scenario configured" % name)
    current = scenario(resolved)
    return current.backend_class, current.make_raw_config()
