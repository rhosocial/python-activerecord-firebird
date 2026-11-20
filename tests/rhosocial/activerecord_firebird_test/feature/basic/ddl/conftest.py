# tests/rhosocial/activerecord_firebird_test/feature/basic/ddl/conftest.py
"""Use the shared ``basic/ddl`` minimal test set.

The shared group has no tables: the ALTER TABLE contracts render expressions
only.  Firebird-specific live checks in this directory use the root
``fb_config`` fixture, which points at this directory's own database file.
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.conftest import *  # noqa: F401,F403
