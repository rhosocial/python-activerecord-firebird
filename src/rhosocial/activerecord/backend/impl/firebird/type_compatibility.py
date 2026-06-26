# src/rhosocial/activerecord/backend/impl/firebird/type_compatibility.py
"""Firebird type casting compatibility checks."""

from typing import Set, Tuple, Optional


DIRECT_COMPATIBLE_CASTS: Set[Tuple[str, str]] = {
    ("varchar", "varchar"),
    ("char", "char"),
    ("integer", "integer"),
    ("bigint", "bigint"),
    ("smallint", "smallint"),
    ("float", "float"),
    ("double precision", "double precision"),
    ("decimal", "decimal"),
    ("numeric", "numeric"),
    ("timestamp", "timestamp"),
    ("date", "date"),
    ("time", "time"),
    ("boolean", "boolean"),
    ("blob", "blob"),
    ("integer", "bigint"),
    ("smallint", "integer"),
    ("smallint", "bigint"),
    ("integer", "decimal"),
    ("float", "double precision"),
    ("varchar", "blob"),
    ("char", "varchar"),
    ("varchar", "char"),
    ("timestamp", "date"),
    ("date", "timestamp"),
}


def check_cast_compatibility(source_type: Optional[str], target_type: str) -> bool:
    if source_type is None:
        return True
    if source_type.lower() == target_type.lower():
        return True
    if (source_type.lower(), target_type.lower()) not in DIRECT_COMPATIBLE_CASTS:
        import warnings
        warnings.warn(
            f"Type cast from '{source_type}' to '{target_type}' may fail or lose data in Firebird.",
            UserWarning,
            stacklevel=3,
        )
    return True


def get_compatible_types(source_type: str) -> Set[str]:
    source_lower = source_type.lower()
    return {target for (source, target) in DIRECT_COMPATIBLE_CASTS if source == source_lower}


__all__ = [
    "DIRECT_COMPATIBLE_CASTS",
    "check_cast_compatibility",
    "get_compatible_types",
]