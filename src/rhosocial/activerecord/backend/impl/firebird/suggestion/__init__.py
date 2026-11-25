# src/rhosocial/activerecord/backend/impl/firebird/suggestion/__init__.py
"""Firebird's concrete backend-suggestion implementations.

These mixins answer the ``suggest_*`` protocols declared in
:mod:`rhosocial.activerecord.backend.suggestion.protocols`. They live under their
own namespace rather than in ``mixins`` because suggestions are not expressions
and not general dialect mixins; the value objects they return come from
:mod:`rhosocial.activerecord.backend.suggestion`.
"""

from .column_reorder_suggestion import FirebirdColumnReorderSuggestionMixin
from .data_type_suggestions import FirebirdDataTypeSuggestionsMixin
from .general_suggestions import (
    FirebirdCreateTableLayoutSuggestionMixin,
    FirebirdStringConcatenationSuggestionMixin,
)
from .generated_value_suggestion import (
    FirebirdGeneratedValueSuggestionMixin,
)
from .partition_add_suggestion import FirebirdPartitionAddSuggestionMixin
from .partition_build_suggestion import FirebirdPartitionBuildSuggestionMixin
from .partition_drop_suggestion import FirebirdPartitionDropSuggestionMixin
from .partition_merge_suggestion import FirebirdPartitionMergeSuggestionMixin
from .partition_retention_suggestion import FirebirdPartitionRetentionSuggestionMixin
from .partition_scheme_change_suggestion import FirebirdPartitionSchemeChangeSuggestionMixin
from .partition_split_suggestion import FirebirdPartitionSplitSuggestionMixin
from .partition_table_alter_suggestion import FirebirdPartitionTableAlterSuggestionMixin
from .partition_table_drop_suggestion import FirebirdPartitionTableDropSuggestionMixin
from .table_constraint_change_suggestion import FirebirdTableConstraintChangeSuggestionMixin
from .table_index_change_suggestion import FirebirdTableIndexChangeSuggestionMixin

__all__ = [
    "FirebirdColumnReorderSuggestionMixin",
    "FirebirdDataTypeSuggestionsMixin",
    "FirebirdCreateTableLayoutSuggestionMixin",
    "FirebirdStringConcatenationSuggestionMixin",
    "FirebirdGeneratedValueSuggestionMixin",
    "FirebirdPartitionAddSuggestionMixin",
    "FirebirdPartitionBuildSuggestionMixin",
    "FirebirdPartitionDropSuggestionMixin",
    "FirebirdPartitionMergeSuggestionMixin",
    "FirebirdPartitionRetentionSuggestionMixin",
    "FirebirdPartitionSchemeChangeSuggestionMixin",
    "FirebirdPartitionSplitSuggestionMixin",
    "FirebirdPartitionTableAlterSuggestionMixin",
    "FirebirdPartitionTableDropSuggestionMixin",
    "FirebirdTableConstraintChangeSuggestionMixin",
    "FirebirdTableIndexChangeSuggestionMixin",
]
