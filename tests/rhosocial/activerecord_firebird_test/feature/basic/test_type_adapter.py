# tests/rhosocial/activerecord_firebird_test/feature/basic/test_type_adapter.py
"""
This is a "bridge" file for the basic features test group, specifically for
type adapter tests.

Its purpose is to import the generic tests from the `rhosocial-activerecord-testsuite`
package and make them discoverable by `pytest` within this project's test run.
"""

# Import the fixture that provides the configured model and backend for type adapter tests.
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    type_adapter_fixtures,
)

# Import all tests from the generic testsuite file.
from rhosocial.activerecord.testsuite.feature.basic.test_type_adapter import *
