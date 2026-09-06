# 表分区

## 概述

Firebird 从 Firebird 3.0 开始支持表分区。

## 分区策略

| 策略 | 说明 | 最低版本 |
|------|------|---------|
| RANGE | 范围分区 | 3.0 |
| LIST | 列表分区 | 3.0 |

## 创建分区

```sql
-- RANGE 分区
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    order_date DATE,
    amount DECIMAL(10,2)
) PARTITION BY RANGE (order_date) (
    PARTITION p2022 VALUES LESS THAN (DATE '2023-01-01'),
    PARTITION p2023 VALUES LESS THAN (DATE '2024-01-01'),
    PARTITION p2024 VALUES LESS THAN (DATE '2025-01-01')
);

-- LIST 分区
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

## 分区管理

```sql
-- 添加分区
ALTER TABLE orders ADD PARTITION p2025 VALUES LESS THAN (DATE '2026-01-01');

-- 删除分区
ALTER TABLE orders DROP PARTITION p2022;
```

## 方言特性检测

```python
if dialect.supports_table_partitioning():
    # Firebird 3.0+: RANGE/LIST 分区
    pass
```

## 另请参阅

- [性能](../troubleshooting/performance.md) — 查询优化

💡 *AI 提示：* "何时应该在 Firebird 中使用表分区？"