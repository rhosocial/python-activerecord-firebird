# tests/rhosocial/activerecord_firebird_test/feature/query/test_cte_query_active_query.py
"""
Bridge file for CTE query active query tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""
from rhosocial.activerecord.testsuite.feature.query.test_cte_query_active_query import (
    TestCTEQueryActiveQuery,
    TestCTEQueryErrorHandling,
    TestCTEQueryExtendedFunctionality,
    TestCTEQuerySyncErrorHandling
)
