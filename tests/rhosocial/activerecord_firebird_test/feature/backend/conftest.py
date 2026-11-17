# tests/rhosocial/activerecord_firebird_test/feature/backend/conftest.py
"""Configuration for the expression / dialect and executing backend tests.

Two things live here, both about *how* these tests run rather than what they
assert.

**Parallel by default.** expression-dialect 12.1: parallel is the test
directory's default configuration, not a flag each run adds, and the construct
layer is exactly the part that qualifies -- every case there builds a node and
renders it, holds no connection, and shares no mutable state. This conftest's
``DECLARATION`` declares ``parallel=False`` for the whole backend area, so
plain rendering directories stay ungrouped and run in unlimited parallel.
``--dist=loadgroup`` (set below) keeps ungrouped cases parallel and honours the
per-directory groups declared by the database-backed directories. Only those
directories declare ``parallel=True`` in their own conftest, which is what pins
them to one worker per scenario: ``--dist=loadscope`` / ``--dist=loadfile``
would bind whole modules together and hide the inter-test dependencies parallel
execution exists to expose.

**Each executing directory owns its database.** The root ``fb_config`` already
derives the logical database from the test directory; this conftest adds the
missing half -- it clears that database once per (scenario, database), before
the directory's first test connects. The directories that use it declare
``parallel=True`` themselves, so parallel workers never reset tables another
worker is using. The construct layer declares nothing of the sort and stays
freely parallel, because it never takes a connection.

A caller who wants a specific worker count keeps it: ``-n 0`` or an explicit
``-n`` leaves the choice alone.
"""

from pathlib import Path

import pytest

import support.firebird

from rhosocial.activerecord.testsuite.pytest_plugin import Declaration
from rhosocial.activerecord.testsuite.pytest_plugin.declarations import database_name

# The backend area is ungrouped by default; only directories that use their own
# database opt in to per-scenario serialisation with their own DECLARATION.
DECLARATION = Declaration(
    parallel=False,
    purpose=(
        "Backend-owned tests: keep construct/render directories freely parallel; "
        "only database-backed directories are pinned to one worker per scenario."
    ),
    passes_means=(
        "Backend tests pass -- pure rendering stays parallel, and database-backed "
        "directories are serialised by their own declaration."
    ),
    fails_means="A backend-owned test failed.",
)

# Databases already cleared in this process, keyed by (scenario, database).
_PREPARED_DATABASES = set()


def _database_for(request) -> str:
    """Derive the logical database the directory owning the test runs in."""
    return database_name(Path(str(request.node.path)).parent)


def _scenario():
    """Return the scenario the executing directories run against."""
    name = next(iter(support.firebird.SCENARIO_MAP), None)
    if name is None:
        raise RuntimeError("No Firebird scenario configured")
    return support.firebird.scenario(name)


def _prepare_database(scenario, database: str) -> None:
    """Clear this directory's database once per scenario.

    A failure is swallowed: the executing fixtures connect afterwards, and the
    ones that are deliberately connection-optional turn an unreachable server
    into a skip rather than an error here.
    """
    key = (getattr(scenario, "name", "default"), database)
    if key in _PREPARED_DATABASES:
        return
    _PREPARED_DATABASES.add(key)
    try:
        scenario.reset_database(database)
    except Exception:
        pass


@pytest.fixture
def fb_config(request):
    """Connection configuration for this directory's own database.

    Overrides the root ``fb_config`` inside the backend-owned area. The root
    fixture creates the directory's database when the server is reachable but
    leaves its contents alone; the executing directories expect a clean one,
    so this variant clears it once per (scenario, database). The scenario is
    the first enabled one, exactly as the root fixture resolves it: these are
    low-level backend cases, not scenario matrix runs.
    """
    scenario = _scenario()
    database = _database_for(request)
    _prepare_database(scenario, database)
    return scenario.make_config(database)


def pytest_configure(config):
    """Turn on xdist unless the caller already chose a worker count."""
    if not config.pluginmanager.hasplugin("xdist"):
        return
    # 0 is xdist's own spelling for "do not distribute"; anything else is a
    # decision the caller made and this hook must not overrule.
    if getattr(config.option, "numprocesses", None) not in (None, 0):
        return
    config.option.numprocesses = "auto"
    config.option.dist = "loadgroup"
