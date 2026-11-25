# src/rhosocial/activerecord/backend/impl/firebird/suggestion/_change_points.py
"""Readers for the frozen projections carried by migration change points.

Core's ``ChangePlan`` hands the backend dialect-neutral projections made by its
``_freeze`` helper: primitives are left alone, expression nodes become
``("params", tuple-of-pairs)`` and everything else becomes ``("repr", text)``.
These readers expose only facts a projection actually states -- a constraint
or index name, a list of plain column names, a boolean option -- so a
suggestion can decline instead of guessing an expression kind or a predicate
that the projection no longer carries. A caller may also pass the original
expression node; its ``get_params()`` is the same fact surface.

``answer`` fills a point's ``operations`` field without losing the rest of its
context; the four points are frozen dataclasses, so a new value is returned.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional

__all__ = [
    "answer",
    "declaration_params",
    "frozen_params",
    "projection",
    "reusable_expression",
]


def answer(point: Any, operations: Any) -> Any:
    """Return ``point`` with its tri-state ``operations`` filled in."""
    if dataclasses.is_dataclass(point):
        return dataclasses.replace(point, operations=operations)
    return point


def frozen_params(value: Any) -> Optional[Dict[str, Any]]:
    """The parameter mapping of a frozen ``("params", ...)`` projection."""
    if not isinstance(value, tuple) or len(value) != 2 or value[0] != "params":
        return None
    pairs = value[1]
    if not isinstance(pairs, tuple) or not all(
        isinstance(pair, tuple) and len(pair) == 2 for pair in pairs
    ):
        return None
    return dict(pairs)


def declaration_params(value: Any) -> Optional[Dict[str, Any]]:
    """Parameters of a frozen projection or of a live expression node."""
    params = frozen_params(value)
    if params is not None:
        return params
    getter = getattr(value, "get_params", None)
    if not callable(getter):
        return None
    try:
        return dict(getter())
    except (AttributeError, TypeError, ValueError):  # pragma: no cover - malformed node
        return None


def projection(value: Any) -> Any:
    """Comparable projection of a declaration value, without rendering SQL.

    This mirrors core's ``_freeze`` so an old/new pair can be compared by the
    same facts the change planner used to decide that the point exists.
    """
    if value is None or isinstance(value, (str, int, float, bool, bytes, tuple)):
        return value
    getter = getattr(value, "get_params", None)
    if callable(getter):
        try:
            return (
                "params",
                tuple(sorted((str(key), projection(item)) for key, item in getter().items())),
            )
        except (AttributeError, TypeError, ValueError):  # pragma: no cover - malformed node
            pass
    if isinstance(value, (list, set, frozenset)):
        return tuple(projection(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), projection(item)) for key, item in value.items()))
    return ("repr", repr(value))


def reusable_expression(value: Any) -> bool:
    """Whether ``value`` is a live node a statement can render directly."""
    return callable(getattr(value, "to_sql", None))
