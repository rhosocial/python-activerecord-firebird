# src/rhosocial/activerecord/backend/impl/firebird/suggestion/__init__.py
"""Firebird's concrete backend-suggestion implementations.

These mixins answer the ``suggest_*`` protocols declared in
:mod:`rhosocial.activerecord.backend.dialect.protocols`. They live under their
own namespace rather than in ``mixins`` because suggestions are not expressions
and not general dialect mixins; the value objects they return come from
:mod:`rhosocial.activerecord.backend.suggestion`.
"""

from .data_type_suggestions import FirebirdDataTypeSuggestionsMixin
from .integer_auto_increment_column_suggestion import (
    FirebirdIntegerAutoIncrementColumnSuggestionMixin,
)
from .partition_add_suggestion import FirebirdPartitionAddSuggestionMixin
from .partition_build_suggestion import FirebirdPartitionBuildSuggestionMixin
from .partition_drop_suggestion import FirebirdPartitionDropSuggestionMixin
from .partition_merge_suggestion import FirebirdPartitionMergeSuggestionMixin
from .partition_retention_suggestion import FirebirdPartitionRetentionSuggestionMixin
from .partition_split_suggestion import FirebirdPartitionSplitSuggestionMixin
from .partition_table_alter_suggestion import FirebirdPartitionTableAlterSuggestionMixin
from .partition_table_drop_suggestion import FirebirdPartitionTableDropSuggestionMixin

__all__ = [
    "FirebirdDataTypeSuggestionsMixin",
    "FirebirdIntegerAutoIncrementColumnSuggestionMixin",
    "FirebirdPartitionAddSuggestionMixin",
    "FirebirdPartitionBuildSuggestionMixin",
    "FirebirdPartitionDropSuggestionMixin",
    "FirebirdPartitionMergeSuggestionMixin",
    "FirebirdPartitionRetentionSuggestionMixin",
    "FirebirdPartitionSplitSuggestionMixin",
    "FirebirdPartitionTableAlterSuggestionMixin",
    "FirebirdPartitionTableDropSuggestionMixin",
]
