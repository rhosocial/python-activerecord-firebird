# src/rhosocial/activerecord/backend/impl/firebird/mixins/partition.py
"""Firebird partition DDL mixin — Firebird does not support partitioning."""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import PartitionClause


class FirebirdPartitionMixin:
    """Firebird partition DDL mixin.

    Firebird does not support table partitioning. All partition-related
    methods raise UnsupportedFeatureError.
    """

    def format_partition_clause(self, expr: "PartitionClause") -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "PARTITION BY clause",
            "Firebird does not support table partitioning. "
            "PartitionClause cannot be used with the Firebird backend.",
        )

    def supports_table_partitioning(self) -> bool:
        return False

    def supports_partitioned_table_creation(self) -> bool:
        return False

    def supports_partition_metadata_introspection(self) -> bool:
        return False

    def supports_range_table_partitioning(self) -> bool:
        return False

    def supports_list_table_partitioning(self) -> bool:
        return False

    def supports_hash_table_partitioning(self) -> bool:
        return False

    def supports_subpartitioning(self) -> bool:
        return False

    def supports_add_partition(self) -> bool:
        return False

    def supports_drop_partition(self) -> bool:
        return False

    def supports_truncate_partition(self) -> bool:
        return False

    def supports_reorganize_partition(self) -> bool:
        return False

    def supports_attach_partition(self) -> bool:
        return False

    def supports_detach_partition(self) -> bool:
        return False
