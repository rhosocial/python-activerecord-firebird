# tests/rhosocial/activerecord_firebird_test/feature/query/test_active_query_range.py
"""
Bridge file for ActiveQuery range tests from the testsuite.

This file imports the generic tests from the testsuite package and makes them
discoverable by pytest in this project's test run.
"""
from rhosocial.activerecord.testsuite.feature.query.test_active_query_range import (
    TestSyncActiveQueryRange
)
