# tests/rhosocial/activerecord_firebird_test/feature/query/worker/test_parallel_queries.py
"""
Bridge file for parallel queries worker tests.

Imports tests from testsuite and makes them discoverable by pytest.
"""
from rhosocial.activerecord.testsuite.feature.query.worker.conftest import (
    order_fixtures_for_worker,
)
from rhosocial.activerecord.testsuite.feature.query.worker.test_parallel_queries import (
    TestParallelQueries
)
