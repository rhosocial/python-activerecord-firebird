# Bridge file for bulk operations tests from the testsuite.
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    bulk_user_class,
)
from rhosocial.activerecord.testsuite.feature.basic.test_bulk_operations import (
    TestSyncBulkCreate,
    TestSyncBulkUpdate,
    TestSyncBulkDelete,
    TestSyncQueryUpdateAll,
    TestSyncQueryDeleteAll,
)
