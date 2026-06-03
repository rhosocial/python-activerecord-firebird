# src/rhosocial/activerecord/backend/impl/firebird/collation.py
"""
Firebird collation names supported by the dialect whitelist.
"""

from enum import Enum
from typing import Optional, Tuple


class FirebirdCollation(Enum):
    """Common Firebird collations for expression-level COLLATE."""

    UNICODE = "UNICODE"
    UNICODE_CI = "UNICODE_CI"
    UNICODE_CI_AI = "UNICODE_CI_AI"


_FIREBIRD_COLLATIONS = {collation.value for collation in FirebirdCollation}


def validate_firebird_collation_name(
    name: str,
    version: Optional[Tuple[int, int, int]] = None,
) -> str:
    normalized = name.upper()
    if normalized not in _FIREBIRD_COLLATIONS:
        raise ValueError(f"Unsupported Firebird collation: {name!r}")
    return normalized
