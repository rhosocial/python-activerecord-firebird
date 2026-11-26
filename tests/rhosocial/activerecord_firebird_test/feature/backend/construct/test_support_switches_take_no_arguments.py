# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/test_support_switches_take_no_arguments.py
"""``supports_*`` is a support switch: no arguments, one bool.

A support switch answers "does this dialect configuration have capability k",
so its only input is the dialect instance. Anything that needs a name or a kind
is either a separate switch (closed vocabulary) or a format-time validation on
the node (open vocabulary) -- never an argument to ``supports_*``.

The scan is static (``ast``) so it sees the declaration even where a test would
have to construct a dialect to call it, and it covers this repository's own
``src`` tree rather than the core package. It also requires the ``-> bool``
annotation: a mapping answer is a catalogue, and belongs under ``suggest_*``.

A second scan guards the same idea from the other side: a ``runtime_checkable``
Protocol is satisfied structurally, so naming one as a base adds nothing but its
``...`` stubs -- and, worse, it puts ``typing.Protocol.__init__`` into the MRO
ahead of the base constructor. No concrete class may inherit a base ending
``Support``; only another protocol may. The protocol remains a declaration to
be checked, not an ancestor.
"""

import ast
from pathlib import Path

import pytest


def _repository_root() -> Path:
    """The repository root that owns this test file and its ``src`` tree."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src").is_dir():
            return parent
    raise AssertionError("could not locate the repository root above this test file")


def _source_files():
    """Every module of this backend's own source tree."""
    root = _repository_root() / "src"
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _required_arguments(func):
    """Parameters that must be passed, excluding ``self``/``cls``."""
    args = func.args
    positional = [*args.posonlyargs, *args.args]
    if positional and positional[0].arg in ("self", "cls"):
        positional = positional[1:]
    required = positional[: len(positional) - len(args.defaults)]
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        if default is None:
            required.append(arg)
    return [arg.arg for arg in required]


def _annotates_bool(func):
    """A switch declares ``-> bool``; a catalogue or mapping is not a switch."""
    annotation = func.returns
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name) and annotation.id == "bool":
        return True
    if isinstance(annotation, ast.Constant) and annotation.value == "bool":
        return True
    return False


def _base_name(base):
    """The spelled name of a base expression: ``Name`` or ``a.b.C``."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _concrete_support_protocol_bases(tree, label):
    """``label:line Class(bases)`` for a concrete class inheriting a Support protocol.

    A class definition that names ``Protocol`` among its bases is itself a
    protocol, and a protocol subclassing another protocol is the one allowed
    shape. Every other class -- dialect, mixin, helper -- is concrete, and
    must not have a ``*Support`` protocol in its bases: the protocol would
    contribute only ``...`` stubs, and its ``__init__`` would take part in
    the MRO.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        names = [_base_name(base) for base in node.bases]
        if "Protocol" in names:
            continue
        offenders = [
            name for name in names if name is not None and name.endswith("Support")
        ]
        if offenders:
            found.append(f"{label}:{node.lineno} {node.name}({', '.join(offenders)})")
    return found


def _offenders(tree, label):
    """``label:line name(params)`` for every support switch that is not a bool switch."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("supports_"):
                continue
            missing = _required_arguments(item)
            if missing:
                found.append(f"{label}:{item.lineno} {item.name}({', '.join(missing)})")
            elif not _annotates_bool(item):
                found.append(f"{label}:{item.lineno} {item.name} does not return bool")
    return found


@pytest.mark.parametrize("path", _source_files(), ids=lambda path: path.name)
def test_support_switch_takes_no_required_argument(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = _offenders(tree, path.name)
    assert not offenders, "\n".join(offenders)


def test_the_scan_reaches_the_source_tree():
    files = _source_files()
    assert files, "no source files were found -- the scan reached nothing"
    assert len(files) > 50, f"only {len(files)} source files were scanned"


def test_the_scan_flags_a_planted_violation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, name):\n"
        "        return False\n",
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    offenders = _offenders(tree, "probe")
    assert offenders, "the scan did not notice a support switch with an argument"
    assert "supports_thing(name)" in offenders[0]


def test_the_scan_flags_a_mapping_annotation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "from typing import Dict\n"
        "class P:\n"
        "    def supports_thing(self) -> Dict[str, bool]:\n"
        "        return {}\n",
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    offenders = _offenders(tree, "probe")
    assert offenders, "the scan did not notice a catalogue spelled as a switch"
    assert "does not return bool" in offenders[0]


def test_the_scan_flags_a_missing_annotation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self):\n"
        "        return False\n",
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    offenders = _offenders(tree, "probe")
    assert offenders, "the scan did not notice an unannotated switch"
    assert "does not return bool" in offenders[0]


def test_the_scan_accepts_a_quoted_bool_annotation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        'class P:\n    def supports_thing(self) -> "bool":\n        return False\n',
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert not _offenders(tree, "probe")


def test_the_scan_accepts_a_defaulted_parameter(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n"
        "    def supports_thing(self, name=None) -> bool:\n"
        "        return False\n",
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert not _offenders(tree, "probe")


def test_no_concrete_class_inherits_a_support_protocol():
    """Only a protocol may inherit a protocol; everyone else implements methods."""
    files = _source_files()
    assert files, "no source files were found -- the scan reached nothing"
    offenders = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders.extend(_concrete_support_protocol_bases(tree, path.name))
    assert not offenders, (
        "a concrete class inherits a *Support protocol, so its `...` stubs are "
        "what isinstance sees instead of a real implementation (and its "
        "``__init__`` joins the MRO):\n" + "\n".join(offenders)
    )


def test_the_scan_flags_a_planted_concrete_violation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class Mixin:\n"
        "    pass\n"
        "\n"
        "class ProbeDialect(Mixin, ExplainSupport):\n"
        "    pass\n"
        "\n"
        "class ProbeSuggestionMixin(ExplainSupport):\n"
        "    pass\n",
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    offenders = _concrete_support_protocol_bases(tree, "probe")
    assert offenders, "the scan did not notice a concrete class inheriting a protocol"
    assert "ProbeDialect(ExplainSupport)" in offenders[0]
    assert "ProbeSuggestionMixin(ExplainSupport)" in offenders[1]


def test_the_scan_allows_protocols_inheriting_protocols(tmp_path):
    """A clean control: protocol inheritance stays a declaration, not a concrete base."""
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "from typing import Protocol\n"
        "\n"
        "class ExplainSupport(Protocol):\n"
        "    pass\n"
        "\n"
        "class DerivedSupport(ExplainSupport, Protocol):\n"
        "    pass\n"
        "\n"
        "class Mixin:\n"
        "    pass\n"
        "\n"
        "class ProbeDialect(Mixin):\n"
        "    pass\n",
        encoding="utf-8",
    )

    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert not _concrete_support_protocol_bases(tree, "probe")
