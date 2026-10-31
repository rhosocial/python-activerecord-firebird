# src/rhosocial/activerecord/backend/impl/firebird/examples/introspection_generators.py
"""Generators, domains and the introspection cache, against a real database.

Run it from the repository root with the worktree's virtual environment::

    .venv3.14/Scripts/python.exe -m \\
        rhosocial.activerecord.backend.impl.firebird.examples.introspection_generators

Connection settings are taken, in order, from:

1. ``FIREBIRD_SCENARIOS_CONFIG_PATH`` pointing at a scenario YAML (the file the
   tests use);
2. ``tests/config/firebird_scenarios.yaml`` in the repository;
3. the ``FIREBIRD_*`` environment variables
   (``FIREBIRD_HOST``, ``FIREBIRD_PORT``, ``FIREBIRD_DATABASE``,
   ``FIREBIRD_USERNAME``, ``FIREBIRD_PASSWORD`` ...).

With no server configured or reachable, nothing is invented: the script prints
what to set and exits non-zero.

What it demonstrates, in order:

* ``list_generators()`` / ``get_generator_info()`` -- Firebird sequences with
  the value they currently hold. The value is read with ``GEN_ID(name, 0)``,
  which increments by zero, so reading does not advance the sequence.
* ``list_domains()`` / ``get_domain_info()`` -- Firebird's reusable type layer,
  with base type, length, charset, nullability, default and check text.
* the introspection cache: the same two calls are made twice, counting the
  statements the introspector executes. The second pass asks the catalogue
  nothing, and only the first pays for it.

Both objects this script creates are dropped again at the end.
"""

import os
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

INSTRUCTIONS = """\
No Firebird server is configured. Point this example at one with either:

  # 1. the scenario file the tests use
  $env:FIREBIRD_SCENARIOS_CONFIG_PATH = 'F:\\...\\tests\\config\\firebird_scenarios.yaml'

  # 2. the same FIREBIRD_* variables the tests read
  $env:FIREBIRD_HOST = '127.0.0.1'
  $env:FIREBIRD_PORT = '3050'
  $env:FIREBIRD_DATABASE = 'C:/data/test.fdb'
  $env:FIREBIRD_USERNAME = 'SYSDBA'
  $env:FIREBIRD_PASSWORD = 'masterkey'

The database must already exist: this example connects to it, and creates and
drops one generator and one domain inside it. It never creates a database.
"""


def _config_from_yaml(path: str) -> Optional[FirebirdConnectionConfig]:
    """Read the first scenario out of a scenario YAML, if it is readable."""
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        scenarios = data.get("scenarios") or {}
        if not scenarios:
            return None
        return FirebirdConnectionConfig(**next(iter(scenarios.values())))
    except Exception:
        return None


def _find_repo_scenario_file() -> Optional[str]:
    """The tests' default scenario file, found by walking up from this module."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tests" / "config" / "firebird_scenarios.yaml"
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_config() -> Optional[FirebirdConnectionConfig]:
    """The connection settings to use, or ``None`` when none are configured."""
    env_path = os.environ.get("FIREBIRD_SCENARIOS_CONFIG_PATH")
    if env_path and os.path.isfile(env_path):
        config = _config_from_yaml(env_path)
        if config is not None:
            return config

    repo_path = _find_repo_scenario_file()
    if repo_path:
        config = _config_from_yaml(repo_path)
        if config is not None:
            return config

    if not os.environ.get("FIREBIRD_DATABASE"):
        return None
    try:
        return FirebirdConnectionConfig.from_env()
    except Exception:
        return None


class _CountingExecutor:
    """Delegate to an introspector executor, counting the statements it runs.

    ``execute`` is the one method both ``SyncIntrospectorExecutor`` and this
    backend's own executor expose, so wrapping it measures every catalogue
    question without touching the introspector that asks them.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.questions = 0

    def execute(self, sql: str, params: tuple = ()) -> Any:
        self.questions += 1
        return self._inner.execute(sql, params)


def _print_rows(label: str, rows: Any) -> None:
    print(f"\n{label}: {len(rows)}")
    for row in rows:
        print(f"  {asdict(row)}")


def _run_against(backend: FirebirdBackend) -> int:
    """Create the demo objects, print both families, and measure the cache."""
    suffix = uuid.uuid4().hex[:8].upper()
    generator_name = f"DEMO_GENERATOR_{suffix}"
    domain_name = f"DEMO_DOMAIN_{suffix}"
    created_generator = False
    created_domain = False

    try:
        backend.execute(f"CREATE GENERATOR {generator_name}", fetch=False)
        created_generator = True
        backend.execute(f"SET GENERATOR {generator_name} TO 1234", fetch=False)

        backend.execute(
            f"CREATE DOMAIN {domain_name} AS VARCHAR(40) CHARACTER SET UTF8 "
            f"NOT NULL DEFAULT 'unspecified' CHECK (VALUE <> '')",
            fetch=False,
        )
        created_domain = True

        introspector = backend.introspector

        # -- the values themselves ---------------------------------------
        generator = introspector.get_generator_info(generator_name)
        print(f"\nGenerator {generator_name} (looked up by name):")
        print(f"  {asdict(generator) if generator else None}")

        domain = introspector.get_domain_info(domain_name)
        print(f"\nDomain {domain_name} (looked up by name):")
        print(f"  {asdict(domain) if domain else None}")

        _print_rows("Generators", introspector.list_generators())
        _print_rows("Domains", introspector.list_domains())

        # -- the cache ---------------------------------------------------
        #
        # Both calls are answered from the cache the introspector owns. The
        # first pass reads the catalogue; the second must not, which is what
        # the statement count shows. Time is reported alongside because a
        # count of zero statements with a slow second pass would mean the
        # cache is not where the saving comes from.
        counting = _CountingExecutor(introspector._executor)
        introspector._executor = counting
        try:
            counting.questions = 0
            started = time.perf_counter()
            cold_generators = introspector.list_generators()
            cold_domains = introspector.list_domains()
            cold_seconds = time.perf_counter() - started
            cold_questions = counting.questions

            counting.questions = 0
            started = time.perf_counter()
            warm_generators = introspector.list_generators()
            warm_domains = introspector.list_domains()
            warm_seconds = time.perf_counter() - started
            warm_questions = counting.questions
        finally:
            introspector._executor = counting._inner

        print("\nCache:")
        print(
            f"  cold: {cold_questions} catalogue statements, "
            f"{cold_seconds * 1000:.1f} ms "
            f"({len(cold_generators)} generators, {len(cold_domains)} domains)"
        )
        print(
            f"  warm: {warm_questions} catalogue statements, "
            f"{warm_seconds * 1000:.1f} ms "
            f"({len(warm_generators)} generators, {len(warm_domains)} domains)"
        )

        if warm_questions != 0:
            print(
                "\nThe second pass still asked the catalogue; the cache is not "
                "returning what it stored.",
                file=sys.stderr,
            )
            return 1

        if not any(g.name == generator_name for g in warm_generators):
            print(f"Generator {generator_name} is missing from the listing.", file=sys.stderr)
            return 1
        if not any(d.name == domain_name for d in warm_domains):
            print(f"Domain {domain_name} is missing from the listing.", file=sys.stderr)
            return 1

        return 0

    finally:
        if created_domain:
            try:
                backend.execute(f"DROP DOMAIN {domain_name}", fetch=False)
            except Exception as exc:  # pragma: no cover - cleanup is best effort
                print(f"Could not drop domain {domain_name}: {exc}", file=sys.stderr)
        if created_generator:
            try:
                backend.execute(f"DROP GENERATOR {generator_name}", fetch=False)
            except Exception as exc:  # pragma: no cover - cleanup is best effort
                print(
                    f"Could not drop generator {generator_name}: {exc}", file=sys.stderr
                )


def main() -> int:
    config = resolve_config()
    if config is None:
        print(INSTRUCTIONS, file=sys.stderr)
        return 2

    backend = FirebirdBackend(connection_config=config)
    try:
        backend.connect()
    except Exception as exc:
        print(f"Could not connect to Firebird: {exc}", file=sys.stderr)
        print(file=sys.stderr)
        print(INSTRUCTIONS, file=sys.stderr)
        return 2

    try:
        version = backend.get_server_version()
        print(f"Connected to Firebird {'.'.join(str(v) for v in version)}")
        print(f"Database: {config.database}")
        return _run_against(backend)
    except Exception as exc:
        print(f"Introspection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            backend.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
