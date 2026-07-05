# tests/rhosocial/activerecord_firebird_test/feature/query/connection/test_cte_query_context.py
"""
CTEQuery Context Test Module for Firebird backend.

This module imports and runs the shared tests from the testsuite package,
ensuring Firebird backend compatibility for CTEQuery connection pool context awareness.
"""
from rhosocial.activerecord.testsuite.feature.query.connection.conftest import (
    sync_pool_and_model,
)

# Import shared tests from testsuite package
from rhosocial.activerecord.testsuite.feature.query.connection.test_cte_query_context import (
    TestSyncCTEQueryContext
)
