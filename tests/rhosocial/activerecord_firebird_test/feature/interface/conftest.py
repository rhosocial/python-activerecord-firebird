# tests/rhosocial/activerecord_firebird_test/feature/interface/conftest.py
"""
Pytest configuration for interface tests.

This file imports fixtures from the corresponding testsuite, making them
available to the tests in this directory.  The shared interface group defines
no fixtures: these tests are database-free and only exercise in-process data
structures, so the directory opens no database and declares no fixture group.
"""

from rhosocial.activerecord.testsuite.feature.interface.conftest import *  # noqa: F403
