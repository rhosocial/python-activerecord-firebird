# src/rhosocial/activerecord/backend/impl/firebird/suggestion/partition.py
"""Firebird's partition-lifecycle suggestions.

Firebird has no native table partitioning and no partition-maintenance
mechanism. Every ``supports_*_partitioning`` / ``supports_add_partition`` /
``supports_drop_partition`` probe is False (see :class:`FirebirdPartitionMixin`),
so there is no mechanism to suggest for any strategy. All eight methods answer
the explicit "unsupported" state (``operations is False``) rather than staying
silent: the caller can report partitioning as unavailable instead of guessing.

Firebird is a pseudo-async backend (firebird-driver has no real async), so only
these synchronous suggestions are meaningful; there is no async counterpart.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion import (
    PartitionAddSuggestion,
    PartitionBuildSuggestion,
    PartitionDropSuggestion,
    PartitionMergeSuggestion,
    PartitionRetentionSuggestion,
    PartitionSplitSuggestion,
    PartitionTableAlterSuggestion,
    PartitionTableDropSuggestion,
)

if TYPE_CHECKING:  # pragma: no cover
    from ....expression import PartitionStrategy


class FirebirdPartitionSuggestionMixin:
    """Answer Firebird's lack of partitioning explicitly at every lifecycle point."""

    def suggest_partition_build(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionBuildSuggestion:
        return PartitionBuildSuggestion(False)

    def suggest_partition_table_drop(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionTableDropSuggestion:
        return PartitionTableDropSuggestion(False)

    def suggest_partition_table_alter(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionTableAlterSuggestion:
        return PartitionTableAlterSuggestion(False)

    def suggest_partition_add(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionAddSuggestion:
        return PartitionAddSuggestion(False)

    def suggest_partition_drop(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionDropSuggestion:
        return PartitionDropSuggestion(False)

    def suggest_partition_split(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionSplitSuggestion:
        return PartitionSplitSuggestion(False)

    def suggest_partition_merge(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionMergeSuggestion:
        return PartitionMergeSuggestion(False)

    def suggest_partition_retention(
        self, strategy: "PartitionStrategy", plan: object
    ) -> PartitionRetentionSuggestion:
        return PartitionRetentionSuggestion(False)
