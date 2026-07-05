# tests/rhosocial/activerecord_firebird_test/feature/basic/worker/test_parallel_crud.py
"""
Bridge file for parallel CRUD worker tests.

Imports tests from testsuite and makes them discoverable by pytest.
"""
from rhosocial.activerecord.testsuite.feature.basic.worker.conftest import (
    user_class_for_worker,
)
from rhosocial.activerecord.testsuite.feature.basic.worker.test_parallel_crud import (
    TestParallelCRUD
)
