# tests/rhosocial/activerecord_firebird_test/feature/basic/connection/conftest.py
"""Use the shared ``basic/connection`` minimal test set.

The pool fixtures build their own database from the environment, so this
directory's contract (imported with the shared group) is what keeps them on
one worker per scenario.
"""

from rhosocial.activerecord.testsuite.feature.basic.connection.conftest import *  # noqa: F401,F403
