# tests/rhosocial/activerecord_firebird_test/feature/backend/conftest.py
"""Configuration for the expression / dialect and executing backend tests.

Two things live here, both about *how* these tests run rather than what they
assert.

**Parallel by default.** expression-dialect 12.1: parallel is the test
directory's default configuration, not a flag each run adds, and the construct
layer is exactly the part that qualifies -- every case there builds a node and
renders it, holds no connection, and shares no mutable state.
``--dist=loadgroup`` keeps every ungrouped case parallel and honours an
explicit ``xdist_group``; ``--dist=loadscope`` / ``--dist=loadfile`` would
bind whole modules together and hide the inter-test dependencies parallel
execution exists to expose.

**Each executing directory owns its database.** The root ``fb_config`` already
derives the logical database from the test directory; this conftest adds the
missing half -- it clears that database once per (scenario, database), before
the directory's first test connects, and pins a directory's items to one
worker so parallel workers never reset tables another worker is using. The
construct layer registers nothing and stays freely parallel, because it never
takes a connection.

A caller who wants a specific worker count keeps it: ``-n 0`` or an explicit
``-n`` leaves the choice alone.
"""

from pathlib import Path

import pytest

import support.firebird

from rhosocial.activerecord.testsuite.core.declarations import database_name

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


def pytest_collection_modifyitems(config, items):
    """Pin a backend directory's tests to one worker.

    These directories create and drop tables in the directory's own database,
    so two workers must never run tests from the same directory at once.
    """
    for item in items:
        parts = item.path.parts
        if "backend" not in parts:
            continue
        item.add_marker(
            pytest.mark.xdist_group("firebird-backend::" + str(item.path.parent))
        )


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
