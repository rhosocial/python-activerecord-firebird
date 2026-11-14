# tests/rhosocial/activerecord_firebird_test/feature/query/core/conftest.py
"""The Firebird-only expression test set.

These tests are backend-specific, so the fixture group lives here rather than
in the shared suite.  The collation test creates and drops the table it uses
itself, so the directory-level contract only creates or clears the database.
"""

from rhosocial.activerecord.testsuite.feature.query.conftest import *  # noqa: F401,F403


def ensure_database(environment):
    """Create the directory's database, or clear it when it already exists."""
    environment.reset_database()


def prepare(environment):
    """Nothing to prepare: the test owns the table it creates."""


def teardown(environment):
    """Nothing to tear down: the test drops the table it created."""
