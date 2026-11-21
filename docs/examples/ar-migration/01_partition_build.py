# docs/examples/ar-migration/01_partition_build.py
"""Offline example: Firebird's explicit "partitioning unsupported" path.

Firebird has no native table partitioning and no partition-maintenance module;
every ``supports_*_partitioning`` / ``supports_add_partition`` /
``supports_drop_partition`` probe is False. All eight ``suggest_partition_*``
methods therefore answer the explicit unsupported state -- ``operations is
False`` -- so a caller can report partitioning as unavailable instead of
guessing at SQL Firebird would reject.

No connection and no ``ctx.apply()`` are used: the script only instantiates a
``FirebirdDialect`` and inspects each suggestion's tri-state ``operations``.

Run with (from the repository root)::

    PYTHONPATH=src python docs/examples/ar-migration/01_partition_build.py
"""

from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.statements import PartitionByRangeClause
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

# (label, method) pairs for all eight partition-lifecycle suggestion points.
LIFECYCLE_POINTS = (
    ("build", "suggest_partition_build"),
    ("table_drop", "suggest_partition_table_drop"),
    ("table_alter", "suggest_partition_table_alter"),
    ("add", "suggest_partition_add"),
    ("drop", "suggest_partition_drop"),
    ("split", "suggest_partition_split"),
    ("merge", "suggest_partition_merge"),
    ("retention", "suggest_partition_retention"),
)


def main():
    dialect = FirebirdDialect()
    strategy = PartitionByRangeClause(dialect, [Column(dialect, "id")])

    print("== Firebird: no table partitioning ==")
    for label, method in LIFECYCLE_POINTS:
        operations = getattr(dialect, method)(strategy, None).operations
        print(f"  {label}: operations is False -> {operations is False} (value: {operations})")


if __name__ == "__main__":
    main()
