# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_table_alter_suggestion.py
"""Firebird's partition table-alter suggestion.

Firebird has no table partitioning, so there is no table-alter mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionTableAlterSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionByClause


class FirebirdPartitionTableAlterSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition table alter."""

    def suggest_partition_table_alter(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionTableAlterSuggestion:
        return PartitionTableAlterSuggestion(False)
