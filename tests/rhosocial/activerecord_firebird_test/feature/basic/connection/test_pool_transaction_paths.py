# tests/rhosocial/activerecord_firebird_test/feature/basic/connection/test_pool_transaction_paths.py
"""
Pool.transaction() dispatch branch contracts for Firebird backend.

Note: Firebird backend has no async support; only the sync testsuite
module is imported.
"""

from rhosocial.activerecord.testsuite.feature.basic.connection.test_pool_transaction_paths import *  # noqa: F403
