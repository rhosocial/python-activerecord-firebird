# tests/rhosocial/activerecord_firebird_test/feature/backend/conftest.py
"""Configuration for the expression / dialect tests.

Two things live here, both about *how* these tests run rather than what they
assert.

**Parallel by default.** expression-dialect 12.1: parallel is the test
directory's default configuration, not a flag each run adds, and the
expression layer is exactly the part that qualifies -- every case here builds
a node and renders it, holds no connection, and shares no mutable state.
``--dist=loadgroup`` keeps every ungrouped case parallel and honours an
explicit ``xdist_group``; ``--dist=loadscope`` / ``--dist=loadfile`` would
bind whole modules together and hide the inter-test dependencies parallel
execution exists to expose.

**The six connected modules are grouped, and that is the one exception.** They
create and drop real tables against the scenario database this backend points
at, which is one database per run rather than one per worker, so two workers
inside a case would collide on table names. Marking them
``xdist_group("live_db")`` puts the whole set on a single worker and lets
everything else spread across the rest. The grouping is the reason, stated
here once, which is what the clause asks for -- it is not a licence to
serialise the directory.

A caller who wants a specific worker count keeps it: ``-n 0`` or an explicit
``-n`` leaves the choice alone.
"""

LIVE_DB_GROUP = "live_db"


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
