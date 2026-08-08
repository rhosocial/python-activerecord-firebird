# tests/rhosocial/activerecord_firebird_test/feature/basic/ddl/test_alter_table_if_exists.py
"""
ALTER TABLE IF [NOT] EXISTS tests (sync) for the Firebird backend.

Thin bridge that runs the shared testsuite contract against the Firebird
dialect, which rejects all three modifiers (Firebird <= 5.0.4).
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.test_alter_table_if_exists import *  # noqa: F403