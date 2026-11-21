# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_retention_suggestion.py
"""Firebird's partition retention suggestion.

Firebird has no table partitioning, so there is no retention mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionRetentionSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionByClause


class FirebirdPartitionRetentionSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition retention."""

    def suggest_partition_retention(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionRetentionSuggestion:
        return PartitionRetentionSuggestion(False)
