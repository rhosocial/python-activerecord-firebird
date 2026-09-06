# EXPLAIN

## 概述

Firebird 提供 EXPLAIN 用于分析查询执行计划。

## 基本用法

### EXPLAIN 语句

```sql
-- 获取执行计划
EXPLAIN SELECT * FROM users WHERE email = 'alice@example.com'

-- 带 JOIN
EXPLAIN SELECT u.name, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.active = 1
```

### 读取执行计划

EXPLAIN 输出显示：

- **表扫描**: 顺序扫描与索引扫描
- **连接方法**: 嵌套循环、哈希连接
- **排序操作**: 内存排序与磁盘排序
- **行估计**: 预期行数与实际行数

## 示例输出

```sql
EXPLAIN SELECT * FROM users WHERE email LIKE '%@example.com%'

-- 输出可能如下：
-- TABLE USERS
--   SCANNED ROWS: 1000
--   FILTER: USERS.EMAIL LIKE '%@example.com%'
--   SORT: NONE
--   ESTIMATED ROWS: 50
```

## 性能分析

### 识别全表扫描

```sql
-- 查找没有使用索引的 SCANNED ROWS
EXPLAIN SELECT * FROM large_table WHERE non_indexed_column = 'value'
```

### 分析连接性能

```sql
-- 检查连接顺序和方法
EXPLAIN SELECT u.name, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
JOIN products p ON o.product_id = p.id
```

### 检查排序操作

```sql
-- 识别昂贵的排序操作
EXPLAIN SELECT * FROM users ORDER BY created_at DESC
```

## 在 Python 中使用 EXPLAIN

```python
# 获取执行计划
result = backend.execute("EXPLAIN SELECT * FROM users WHERE email = ?", ('test@example.com',))
print(result)

# 分析多个查询
queries = [
    "SELECT * FROM users WHERE id = 1",
    "SELECT * FROM users WHERE email LIKE '%@example.com%'",
    "SELECT u.*, o.* FROM users u JOIN orders o ON u.id = o.user_id"
]

for query in queries:
    plan = backend.execute(f"EXPLAIN {query}")
    print(f"查询: {query[:50]}...")
    print(f"计划: {plan}")
    print()
```

## 优化提示

### 添加缺少的索引

```sql
-- 如果 EXPLAIN 显示全表扫描
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com'
-- 如果输出显示 SCANNED ROWS: 10000，考虑添加索引：
CREATE INDEX idx_users_email ON users (email)
```

### 重写查询

```sql
-- 而不是：
SELECT * FROM users WHERE YEAR(created_at) = 2026

-- 使用：
SELECT * FROM users WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01'
```

### 优化连接

```sql
-- 确保连接列已索引
CREATE INDEX idx_orders_user_id ON orders (user_id)
CREATE INDEX idx_orders_product_id ON orders (product_id)
```

## 常见 EXPLAIN 模式

### 好的计划指标

- 索引使用 (IDX_*)
- 低行估计
- 高效的连接顺序

### 不好的计划指标

- 大表上的全表扫描
- 高行估计
- 昂贵的排序操作

💡 *AI 提示:* "如何解释 Firebird EXPLAIN 输出以优化查询？"