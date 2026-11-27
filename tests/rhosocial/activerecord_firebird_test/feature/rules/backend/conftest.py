# tests/rhosocial/activerecord_firebird_test/feature/rules/backend/conftest.py
"""Fixtures for Firebird's own rule suite.

Firebird owns only its own ``impl/firebird`` tree. Every path is derived from
the installed packages, never from a hardcoded worktree path, and
``source_roots`` names a single root: ``backend/impl/firebird``. The shared
rule library supplies the assertions; this conftest selects the subject.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Iterator, List, Tuple

import pytest

from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import *  # noqa: F401,F403
from rhosocial.activerecord.testsuite.feature.rules.backend import (
    test_no_raw_sql_in_src as raw_sql_rules,
    test_no_reflection_in_expression_layer as reflection_rules,
)
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    uses_database=False,
    parallel=False,
    purpose="Executable assertions of the Firebird backend's formal constraints",
    passes_means="Firebird source obeys the mechanical and structural rule",
    fails_means="Firebird source introduces a forbidden construct or dependency",
)


def firebird_expression_package() -> object:
    """The installed Firebird expression package."""
    return importlib.import_module("rhosocial.activerecord.backend.impl.firebird.expression")


def firebird_impl_root() -> Path:
    """The installed ``backend/impl/firebird`` directory."""
    package = firebird_expression_package()
    for search_path in vars(package).get("__path__", ()):
        current = Path(search_path).resolve()
        for candidate in [current] + list(current.parents):
            if candidate.name == "impl" and candidate.parent.name == "backend":
                return candidate / current.relative_to(candidate).parts[0]
    pytest.skip("Firebird impl root is not discoverable from the installed package")


def firebird_project_root() -> Path:
    """Project root inferred from the installed Firebird package layout."""
    impl_root = firebird_impl_root()
    for candidate in [impl_root] + list(impl_root.parents):
        if (candidate / "tests").is_dir() and (candidate / "src").is_dir():
            return candidate
    pytest.skip("Firebird project root is not discoverable from the installed package")


def python_files_in(root: Path) -> Iterator[Path]:
    """Sorted Python files below *root*, excluding bytecode caches."""
    if root.is_dir():
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


@pytest.fixture
def backend_expression_package() -> object:
    """Firebird's expression package."""
    return firebird_expression_package()


@pytest.fixture
def backend_dialect() -> object:
    """An instantiated Firebird dialect."""
    from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

    return FirebirdDialect()


@pytest.fixture
def backend_prefix() -> str:
    """Firebird's own naming prefix."""
    return "Firebird"


@pytest.fixture
def backend_impl_root() -> Path:
    """The Firebird ``impl`` root used by file-driven shared rules."""
    return firebird_impl_root()


@pytest.fixture
def source_roots() -> List[Tuple[str, Path]]:
    """One root only: the Firebird backend, never core or another backend."""
    return [("firebird", firebird_impl_root())]


@pytest.fixture
def backend_project_root() -> Path:
    """Project root for Firebird's tests."""
    return firebird_project_root()


@pytest.fixture
def backend_test_files(backend_project_root) -> List[Path]:
    """Every Python test file in the Firebird project."""
    files = list(python_files_in(backend_project_root / "tests"))
    assert files, f"no test files under {backend_project_root / 'tests'}"
    return files


def declares_unconstructible(path: Path) -> bool:
    """Whether a file actually assigns UNCONSTRUCTIBLE, not just mentions it."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else ([node.target] if isinstance(node, ast.AnnAssign) else [])
        )
        if any(isinstance(t, ast.Name) and t.id == "UNCONSTRUCTIBLE" for t in targets):
            return True
    return False


@pytest.fixture
def backend_matrix_files(backend_test_files) -> List[Path]:
    """Round-trip matrices that declare an UNCONSTRUCTIBLE assignment.

    The shared harness and this conftest only mention the marker in prose or
    in a filename filter; they expose no matrix facts and are not candidates.
    Firebird's real matrix declares an explicitly empty pin list together with
    two exact comparisons, which the shared rule accepts as two-way facts.
    """
    return [
        path
        for path in backend_test_files
        if "UNCONSTRUCTIBLE" in path.read_text(encoding="utf-8") and declares_unconstructible(path)
    ]


# Measured legacy sites in this backend. Every key carries the exact observed
# count and a reason saying what non-expression object is probed and why no
# declared attribute can replace the probe. Line shifts do not change a key;
# a new call or a new location does.
FIREBIRD_REFLECTION_ENTRIES = {
    ("firebird", "async_transaction.py", "AsyncFirebirdTransactionManager", "getattr"): (
        1,
        "async executor is held by the backend wrapper, not an expression; the wrapper declares no "
        "executor attribute, so the injected optional _executor is read by name",
    ),
    ("firebird", "backend/async_backend.py", "AsyncFirebirdBackend", "getattr"): (
        6,
        "config, cursor and transaction objects are driver-owned, not expressions; "
        "user/timezone/main_transaction/is_active/rowcount/lastrowid are optional across driver "
        "versions and not declared on every object",
    ),
    ("firebird", "backend/async_backend.py", "AsyncFirebirdBackend", "hasattr"): (
        1,
        "config is a caller-supplied driver config object, not an expression; its version attribute "
        "is optional and absent on plain configs",
    ),
    ("firebird", "backend/backend.py", "FirebirdBackend", "getattr"): (
        8,
        "driver cursor, statement metadata and transaction objects are not expressions; "
        "_stmt/_out_desc/_names/datatype/rowcount/lastrowid/main_transaction/is_active have no "
        "declared attribute on every driver version",
    ),
    ("firebird", "backend/backend.py", "FirebirdBackend", "hasattr"): (
        1,
        "config is a caller-supplied driver config object, not an expression; the optional version "
        "flag is not declared on plain configs",
    ),
    ("firebird", "cli/connection.py", "resolve_connection_config_from_args", "getattr"): (
        4,
        "argparse namespace is a CLI value bag, not an expression; "
        "is_async/named_connection/connection_params/charset/role are switches declared only by "
        "argparse when supplied",
    ),
    ("firebird", "cli/connection.py", "warn_if_async_requested", "getattr"): (
        1,
        "argparse namespace has no declared is_async attribute until the switch is supplied; the "
        "probed object is a CLI value bag, not an expression",
    ),
    ("firebird", "cli/info.py", "check_protocol_support", "getattr"): (
        1,
        "the capability name comes from an argparse switch; neither the CLI value bag nor the dialect "
        "declares an attribute for a runtime-chosen name",
    ),
    ("firebird", "cli/info.py", "check_protocol_support", "hasattr"): (
        1,
        "capabilities are contributed by mixins to the dialect, not declared on the CLI object; the "
        "dynamically named switch must be probed before it is read",
    ),
    ("firebird", "cli/info.py", "handle", "getattr"): (
        2,
        "argparse database/version switches are optional and undeclared until supplied; the namespace "
        "is a CLI value bag, not an expression",
    ),
    ("firebird", "cli/introspect.py", "_note_unmeasured_profiles", "getattr"): (
        3,
        "profile statistics come from driver introspection, not an expression; "
        "distinct_count/min_value/max_value have no declared attribute on the several profile shapes",
    ),
    ("firebird", "cli/introspect.py", "_refuse_unused_arguments", "getattr"): (
        3,
        "argparse column/right_table/right_column switches have no declared attribute until supplied; "
        "the probed object is a CLI value bag, not an expression",
    ),
    ("firebird", "cli/introspect.py", "_require_capability", "getattr"): (
        2,
        "the capability switch is chosen by an argparse value; no declared attribute names a "
        "runtime-selected dialect capability and the CLI object is not an expression",
    ),
    ("firebird", "cli/introspect.py", "_serialize_for_output", "hasattr"): (
        1,
        "result rows are plain pydantic/dataclass objects, not expressions; model_dump exists on only "
        "one shape, so no shared declared hook exists",
    ),
    ("firebird", "cli/introspect.py", "_value_sample_arguments", "getattr"): (
        1,
        "argparse limit is an optional switch with no declared attribute until supplied; the "
        "namespace is a CLI value bag, not an expression",
    ),
    ("firebird", "cli/introspect.py", "handle", "getattr"): (
        2,
        "argparse database/is_async switches are optional and undeclared until supplied; the probed "
        "namespace is not an expression",
    ),
    ("firebird", "cli/named_connection.py", "handle", "getattr"): (
        2,
        "argparse output/rich_ascii switches are optional and undeclared until supplied; the probed "
        "namespace is a CLI value bag, not an expression",
    ),
    ("firebird", "cli/named_expression.py", "_get_requested_version", "getattr"): (
        1,
        "argparse dialect_version is an optional switch with no declared attribute until supplied; "
        "the probed namespace is not an expression",
    ),
    ("firebird", "cli/named_expression.py", "handle", "getattr"): (
        1,
        "argparse is_async is an optional switch with no declared attribute until supplied; the "
        "probed namespace is not an expression",
    ),
    ("firebird", "cli/named_migration.py", "disconnect", "getattr"): (
        1,
        "the named migration target is a user object wrapping a backend connection, not an "
        "expression; the protocol declares no _connection attribute",
    ),
    ("firebird", "cli/named_migration.py", "disconnect_async", "getattr"): (
        1,
        "async cleanup reads the same driver-owned optional connection; the user object declares no "
        "async connection attribute to read instead",
    ),
    ("firebird", "cli/named_migration.py", "handle", "getattr"): (
        1,
        "argparse is_async is optional and undeclared until supplied; the probed namespace is a CLI "
        "value bag, not an expression",
    ),
    ("firebird", "cli/named_procedure.py", "handle", "getattr"): (
        1,
        "argparse is_async is optional and undeclared until supplied; the probed namespace is a CLI "
        "value bag, not an expression",
    ),
    ("firebird", "cli/named_procedure_graph.py", "handle", "getattr"): (
        1,
        "argparse is_async is optional and undeclared until supplied; the probed namespace is a CLI "
        "value bag, not an expression",
    ),
    ("firebird", "cli/query.py", "handle", "getattr"): (
        2,
        "log levels are named constants on the logging module and is_async is an optional argparse "
        "switch; neither object is an expression nor declares the runtime-chosen names",
    ),
    ("firebird", "cli/status.py", "_display_status_rich", "hasattr"): (
        3,
        "session/connections/storage groups are optional sections of a status snapshot assembled from "
        "driver introspection, not expression fields; no declared group exists on every status shape",
    ),
    ("firebird", "cli/status.py", "_serialize_for_output", "hasattr"): (
        1,
        "status rows are plain result objects, not expressions; model_dump exists on only one of the "
        "pydantic/dataclass shapes, so no declared hook is shared",
    ),
    ("firebird", "cli/status.py", "handle", "getattr"): (
        2,
        "argparse database/is_async switches are optional and undeclared until supplied; the probed "
        "namespace is not an expression",
    ),
    ("firebird", "examples/introspection_catalog.py", "main", "hasattr"): (
        1,
        "the example reads an optional server_version off a driver connection; the example object is "
        "not an expression and declares no connection attribute",
    ),
    (
        "firebird",
        "introspection/async_introspector.py",
        "FirebirdAsyncIntrospectorMixin",
        "getattr",
    ): (
        2,
        "the backend config and introspected column rows are driver-owned, not expressions; dialect "
        "and data_type_full are absent from some config/result shapes with no declared attribute",
    ),
    (
        "firebird",
        "introspection/status_introspector.py",
        "AsyncFirebirdStatusIntrospector",
        "getattr",
    ): (
        3,
        "backend config charset/username/database are optional on caller-supplied config objects, not "
        "expression fields; no declared config interface exists",
    ),
    (
        "firebird",
        "introspection/status_introspector.py",
        "AsyncFirebirdStatusIntrospector",
        "hasattr",
    ): (
        1,
        "a driver result carries data only on some status queries; the result object is not an "
        "expression and declares no uniform data attribute",
    ),
    ("firebird", "introspection/status_introspector.py", "FirebirdStatusIntrospector", "getattr"): (
        3,
        "backend config charset/username/database are optional on caller-supplied config objects, not "
        "expression fields; no declared config interface exists",
    ),
    ("firebird", "introspection/status_introspector.py", "FirebirdStatusIntrospector", "hasattr"): (
        1,
        "a driver result carries data only on some status queries; the result object is not an "
        "expression and declares no uniform data attribute",
    ),
    ("firebird", "mixins/backend_mixin.py", "FirebirdBackendMixin", "getattr"): (
        6,
        "connector errors and statement handles are driver-owned, not expressions; sqlstate, "
        "gds_codes, errno-style attributes and _in_meta/_in_cnt are optional across driver versions "
        "with no declared attribute",
    ),
    ("firebird", "mixins/backend_mixin.py", "FirebirdBackendMixin", "hasattr"): (
        1,
        "config is caller-supplied and not an expression; its version flag is optional and not "
        "declared on every config object",
    ),
    ("firebird", "mixins/collation.py", "FirebirdCollationMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the expression "
        "only supplies collation_name, so the dialect is the probed object",
    ),
    ("firebird", "mixins/comment.py", "FirebirdCommentMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the COMMENT expression",
    ),
    ("firebird", "mixins/concurrency.py", "FirebirdConcurrencyMixin", "getattr"): (
        1,
        "pool_size is optional on a caller-supplied config object, not an expression field; the "
        "config declares no uniform pool_size attribute",
    ),
    ("firebird", "mixins/database.py", "FirebirdDatabaseMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not a database expression",
    ),
    (
        "firebird",
        "mixins/ddl_alter_table_modifier.py",
        "FirebirdAlterTableModifierMixin",
        "getattr",
    ): (
        2,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the ALTER action",
    ),
    ("firebird", "mixins/dml.py", "FirebirdDMLOperationMixin", "getattr"): (
        3,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the DML expression",
    ),
    ("firebird", "mixins/exception.py", "FirebirdExceptionMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the EXCEPTION expression",
    ),
    ("firebird", "mixins/external_function.py", "FirebirdExternalFunctionMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the function expression",
    ),
    ("firebird", "mixins/introspection.py", "FirebirdIntrospectionMixin", "getattr"): (
        1,
        "opaque_columns is optional on introspected catalogue relation objects, not on an expression; "
        "relation kinds share no declared opaque-columns attribute",
    ),
    ("firebird", "mixins/namespace.py", "FirebirdNamespaceMixin", "getattr"): (
        2,
        "the probe reads schema_name/catalog_name off a catalogue object, not an expression; those "
        "slots are absent on unqualified names and no declared attribute covers every object kind",
    ),
    ("firebird", "mixins/package.py", "FirebirdPackageMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the package expression",
    ),
    ("firebird", "mixins/role.py", "FirebirdRoleMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the role expression",
    ),
    ("firebird", "mixins/routine.py", "FirebirdRoutineMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the routine expression",
    ),
    ("firebird", "mixins/types.py", "FirebirdTypeSupportMixin", "getattr"): (
        2,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the data-type expression",
    ),
    ("firebird", "mixins/user.py", "FirebirdUserMixin", "getattr"): (
        1,
        "version is composed on the dialect at runtime and not declared on this mixin; the probed "
        "object is the dialect, not the user expression",
    ),
    ("firebird", "suggestion/_change_points.py", "declaration_params", "getattr"): (
        1,
        "the value is an arbitrary schema-snapshot entry, not an expression; get_params exists only "
        "on expression-shaped values and plain values declare no such hook",
    ),
    ("firebird", "suggestion/_change_points.py", "projection", "getattr"): (
        1,
        "the value is an arbitrary schema-snapshot entry, not an expression; get_params is absent on "
        "plain values, which declare no shared hook",
    ),
    ("firebird", "suggestion/_change_points.py", "reusable_expression", "getattr"): (
        1,
        "the value comes from a schema snapshot rather than the expression tree; to_sql is optional "
        "on plain values and no declared interface guarantees it",
    ),
}

# RawSQLPredicate is mentioned twice in the DOMAIN payload module: once in the
# legacy string-check import and once in the isinstance guard on the trusted
# CHECK condition. The caller vouches for that text; a declared predicate
# cannot replace it because the legacy `check` argument is a raw SQL string.
FIREBIRD_RAWSQL_ENTRIES = {
    ("firebird", "expression/ddl/domain.py", "RawSQLPredicate"): (
        2,
        "DOMAIN CHECK carries caller-vouched SQL text; the legacy check argument is a string, so a "
        "declared predicate object cannot express it, and the second mention only type-checks that "
        "payload",
    ),
}

#: The shipped quickstart's constant connectivity probe. It is static SQL
#: supplied by the example, not assembled from user input, and an example has
#: no declared attribute that can carry a SQL literal.
FIREBIRD_EXEC_ENTRIES = {
    (
        "firebird",
        "examples/connection/quickstart.py",
        "main",
        "execute",
        "SELECT 1 FROM RDB$DATABASE",
    ): (
        1,
        "shipped example runs a constant capability probe with caller-vouched static SQL; the example "
        "object declares no attribute that can carry a SQL literal",
    ),
}


@pytest.fixture
def reflection_allowlist():
    """Core's baseline plus Firebird's measured, reason-bearing legacy sites."""
    return {**reflection_rules.REFLECTION_ALLOWLIST, **FIREBIRD_REFLECTION_ENTRIES}


@pytest.fixture
def raw_sql_allowlist():
    """Core's baseline plus Firebird's caller-vouched DOMAIN CHECK mention."""
    return {**raw_sql_rules.RAWSQL_ALLOWLIST, **FIREBIRD_RAWSQL_ENTRIES}


@pytest.fixture
def exec_allowlist():
    """Core's baseline plus the quickstart's constant probe literal.

    ``minimum_observed_calls`` is left at the shared default: Firebird exposes
    96 reflection observations after the production fixes, so no lowering is
    needed. Formatter code was repaired rather than allowlisted; all nine
    SQL-text sites now escape declared atoms in named helpers.
    """
    return {**raw_sql_rules.EXEC_ALLOWLIST, **FIREBIRD_EXEC_ENTRIES}
