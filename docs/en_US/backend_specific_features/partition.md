# Table Partitioning

## Overview

Firebird supports table partitioning starting from Firebird 3.0.

## Partitioning Strategies

| Strategy | Description | Minimum Version |
|----------|-------------|-----------------|
| RANGE | Range partitioning | 3.0 |
| LIST | List partitioning | 3.0 |

## Creating Partitions

```sql
-- RANGE partitioning
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    order_date DATE,
    amount DECIMAL(10,2)
) PARTITION BY RANGE (order_date) (
    PARTITION p2022 VALUES LESS THAN (DATE '2023-01-01'),
    PARTITION p2023 VALUES LESS THAN (DATE '2024-01-01'),
    PARTITION p2024 VALUES LESS THAN (DATE '2025-01-01')
);

-- LIST partitioning
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    region VARCHAR(20)
) PARTITION BY LIST (region) (
    PARTITION p_north VALUES ('north'),
    PARTITION p_south VALUES ('south'),
    PARTITION p_east VALUES ('east'),
    PARTITION p_west VALUES ('west')
);
```

## Partition Management

```sql
-- Add partition
ALTER TABLE orders ADD PARTITION p2025 VALUES LESS THAN (DATE '2026-01-01');

-- Drop partition
ALTER TABLE orders DROP PARTITION p2022;
```

## Dialect Feature Detection

```python
if dialect.supports_table_partitioning():
    # Firebird 3.0+: RANGE/LIST partitioning
    pass
```

## See Also

- [Performance](../troubleshooting/performance.md) — Query optimization

💡 *AI Prompt:* "When should I use table partitioning in Firebird?"