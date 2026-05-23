"""
Test bridge for relation cache functionality.

This test file runs the relation cache tests from the testsuite using the Firebird backend.
"""
import pytest


# Import the test classes from the testsuite
from rhosocial.activerecord.testsuite.feature.relation.test_cache import TestRelationCache


# This will cause pytest to run all the tests in the imported class
# The tests will use the fixtures and providers configured in conftest.py
