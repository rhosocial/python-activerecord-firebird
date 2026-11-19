# tests/rhosocial/activerecord_firebird_test/feature/query_integration/test_active_query_set_operation_async.py
"""
Bridge file for async ActiveQuery + SetOperationQuery combination tests from the testsuite.
"""

import importlib

import pytest

_SHARED = (
    "rhosocial.activerecord.testsuite.feature.query_integration."
    "test_active_query_set_operation_async"
)
try:
    _module = importlib.import_module(_SHARED)
except ImportError:
    pytest.skip(
        "async ActiveQuery + SetOperationQuery testsuite not available", allow_module_level=True
    )

# Compatibility shim for testsuite commit 68d4f4f: the shared test_explain
# contract calls pytest.skip() on the supports_explain_plan()==False branch but
# never imports pytest. SQLite CI never noticed (its gate is open, so the line
# never runs); on Firebird the branch executes and raises NameError instead of
# skipping. Inject pytest into the shared module's globals so the capability
# gate skips cleanly. Drop this shim once the testsuite imports pytest itself.
if not hasattr(_module, "pytest"):
    _module.pytest = pytest

globals().update({name: value for name, value in vars(_module).items() if not name.startswith("_")})
