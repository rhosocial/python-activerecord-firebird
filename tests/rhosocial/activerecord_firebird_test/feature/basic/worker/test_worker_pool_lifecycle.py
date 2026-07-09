# tests/rhosocial/activerecord_firebird_test/feature/basic/worker/test_worker_pool_lifecycle.py
"""
Bridge file for worker pool lifecycle tests.

Imports tests from testsuite and makes them discoverable by pytest.
"""
from rhosocial.activerecord.testsuite.feature.basic.worker.conftest import (
    user_class_for_worker,
)
from rhosocial.activerecord.testsuite.feature.basic.worker.test_worker_pool_lifecycle import *
from rhosocial.activerecord.testsuite.feature.basic.worker.test_worker_pool_lifecycle_async import *  # noqa: F403

