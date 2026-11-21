# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_table_drop_suggestion.py
"""Firebird's partition table-drop suggestion.

Firebird has no table partitioning, so there is no table-drop mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionTableDropSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionStrategy


class FirebirdPartitionTableDropSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition table drop."""

    def suggest_partition_table_drop(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionTableDropSuggestion:
        return PartitionTableDropSuggestion(False)
