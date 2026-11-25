# tests/test_src_is_regex_free.py
"""Guard: this repository's ``src`` must not use the ``re`` module.

Project rule: the library parses its few fixed spellings with character scans,
so ``src`` may not import ``re`` and may not call anything through an ``re``
module reference. Tests keep their regular expressions -- they only assert on
generated SQL -- so this guard walks ``src`` and nothing else.

Two independent checks, because either one alone can be fooled: the AST sees
every import form (``import re``, ``from re import ...``, ``import re as ...``,
and a late ``__import__``), while the text scan sees attribute use that reached
a file without an import.
"""

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

#: Any attribute reached through the bare name ``re``.
_REGEX_ATTRIBUTE_USE = re.compile(r"\bre\.(?:[A-Za-z_][A-Za-z0-9_]*)")


def _source_files():
    """Every Python file of this repository's ``src``, sorted for stable ids."""
    return sorted(SRC.rglob("*.py"))


def _offending_imports(path):
    """Import and attribute sites in *path*, as one line each."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re" or alias.name.startswith("re."):
                    offenders.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "re" or module.startswith("re."):
                offenders.append(f"{path}:{node.lineno}: from {module} import ...")
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "re":
                offenders.append(f"{path}:{node.lineno}: re.{node.attr}")
        elif isinstance(node, ast.Call):
            # ``__import__("re")`` and ``import_module("re")`` bypass the
            # syntax the checks above look at.
            called = node.func
            if isinstance(called, ast.Name) and called.id == "__import__":
                name = node.args[0] if node.args else None
            elif isinstance(called, ast.Attribute) and called.attr == "import_module":
                name = node.args[0] if node.args else None
            else:
                name = None
            if isinstance(name, ast.Constant) and isinstance(name.value, str):
                if name.value == "re" or name.value.startswith("re."):
                    offenders.append(f"{path}:{node.lineno}: dynamic import of {name.value!r}")
    return offenders


def test_src_never_imports_the_regex_module():
    offenders = []
    for path in _source_files():
        offenders.extend(_offending_imports(path))
    assert not offenders, (
        "src must not use the re module; reimplement the %d site(s) with "
        "string scanning:\n%s" % (len(offenders), "\n".join(offenders))
    )


def test_src_contains_no_regex_attribute_use():
    """Text backstop: no ``re.compile``-style attribute anywhere, comments too.

    The AST check above is precise; this one is deliberately blunt, so a helper
    named ``re.<something>`` cannot sit in a comment or docstring either.
    """
    offenders = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        for match in _REGEX_ATTRIBUTE_USE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path}:{line}: {match.group(0)}")
    assert not offenders, "src must not reference the re module by attribute:\n%s" % "\n".join(
        offenders
    )
