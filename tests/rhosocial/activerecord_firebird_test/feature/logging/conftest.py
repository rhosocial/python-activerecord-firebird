# tests/rhosocial/activerecord_firebird_test/feature/logging/conftest.py
"""The ``logging`` directory's minimal test set.

Every test here uses fake connections and cursors, so there is no fixture
group: the contract exists only so the directory is a first-class leaf of the
suite.  No database is opened unless a test asks for the environment.
"""


def ensure_database(environment):
    """Create the directory's database, or clear it when it already exists."""
    environment.reset_database()


def prepare(environment):
    """Create the group's tables before every test (none here)."""


def teardown(environment):
    """Drop the group's tables after every test (none here)."""
