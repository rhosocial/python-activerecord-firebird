# src/rhosocial/activerecord/backend/impl/firebird/suggestion/__init__.py
"""Firebird's concrete backend-suggestion implementations.

These mixins answer the ``suggest_*`` protocols declared in
:mod:`rhosocial.activerecord.backend.dialect.protocols`. They live under their
own namespace rather than in ``mixins`` because suggestions are not expressions
and not general dialect mixins; the value objects they return come from
:mod:`rhosocial.activerecord.backend.suggestion`.
"""

from .data_types import FirebirdDataTypeSuggestionsMixin
from .integer_auto_increment import FirebirdIntegerAutoIncrementColumnSuggestionMixin
from .partition import FirebirdPartitionSuggestionMixin

__all__ = [
    "FirebirdDataTypeSuggestionsMixin",
    "FirebirdIntegerAutoIncrementColumnSuggestionMixin",
    "FirebirdPartitionSuggestionMixin",
]
