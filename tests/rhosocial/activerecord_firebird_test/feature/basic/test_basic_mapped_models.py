# tests/rhosocial/activerecord_firebird_test/feature/basic/test_basic_mapped_models.py
# File path: tests/rhosocial/activerecord_firebird_test/feature/basic/test_basic_mapped_models.py

"""
This bridge file imports the `mapped_models_fixtures` from the testsuite's basic feature
conftest and then wildcard imports all test cases related to mapped models
from the testsuite.

IMPORTANT:
- Do NOT add any test logic directly in this file.
- This file is solely responsible for wiring up the testsuite's generic tests
  with the backend's specific fixtures and configuration.
"""
import pytest
from rhosocial.activerecord.testsuite.feature.basic.conftest import mapped_models_fixtures

# Wildcard import all test cases from the testsuite's test file.
from rhosocial.activerecord.testsuite.feature.basic.test_example_basic_fixtures import *

# You can optionally add a fixture here if needed to ensure specific setup/teardown
# for ALL basic_mapped_models tests in this backend, but generally this should be handled
# by the provider and the testsuite's conftest.
