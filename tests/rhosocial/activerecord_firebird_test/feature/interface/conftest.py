# tests/rhosocial/activerecord_firebird_test/feature/interface/conftest.py
"""The ``interface`` directory's minimal test set.

The shared interface group defines no fixtures; these tests are database-free
and only exercise the thread-safe mapping.  The empty contract keeps the
directory a first-class leaf of the suite without opening a database.
"""

from rhosocial.activerecord.testsuite.feature.interface.conftest import *  # noqa: F401,F403


def ensure_database(environment):
    """Create the directory's database, or clear it when it already exists."""
    environment.reset_database()


def prepare(environment):
    """Create the group's tables before every test (none here)."""


def teardown(environment):
    """Drop the group's tables after every test (none here)."""
