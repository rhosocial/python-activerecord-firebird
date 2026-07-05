import pytest
from rhosocial.activerecord.testsuite.feature.basic.test_crud import (
    TestSyncCRUD
)


# Skip test_update_user due to Firebird TIMESTAMP precision limitation
# Firebird TIMESTAMP stores with 100μs (0.0001s) precision, but the test
# expects 1μs precision. This causes a microsecond rounding mismatch
# when comparing original and refreshed timestamps.
# Tracked at: https://github.com/rhosocial/python-activerecord-firebird/issues
TestSyncCRUD.test_update_user = pytest.mark.skip(
    reason="Firebird TIMESTAMP has 100μs precision, test expects 1μs"
)(TestSyncCRUD.test_update_user)
