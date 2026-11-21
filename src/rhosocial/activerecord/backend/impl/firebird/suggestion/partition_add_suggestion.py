# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition_add_suggestion.py
"""Firebird's partition add suggestion.

Firebird has no table partitioning, so there is no add-partition mechanism to
suggest for any strategy. The answer is the explicit "unsupported" state
(``operations is False``), not silence: the caller can report it as unavailable
rather than guessing at SQL the server rejects. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import PartitionAddSuggestion

from ._common import FirebirdPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ._common import PartitionStrategy


class FirebirdPartitionAddSuggestionMixin(FirebirdPartitionSuggestionBase):
    """Answer Firebird's lack of partitioning explicitly at partition add."""

    def suggest_partition_add(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionAddSuggestion:
        return PartitionAddSuggestion(False)
