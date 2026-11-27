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


@pytest.fixture
def backend_matrix_files(backend_test_files) -> List[Path]:
    """Round-trip matrices that declare an UNCONSTRUCTIBLE list."""
    return [
        path
        for path in backend_test_files
        if "UNCONSTRUCTIBLE" in path.read_text(encoding="utf-8")
    ]
