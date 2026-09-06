# 索引

## 概述

Firebird 支持多种索引类型，用于优化查询性能。

## 标准索引

### 创建索引

```sql
-- 基本索引
CREATE INDEX idx_users_email ON users (email)

-- 唯一索引
CREATE UNIQUE INDEX idx_users_username ON users (username)

-- 复合索引
CREATE INDEX idx_users_name_email ON users (name, email)
```

### 索引选项

```sql
-- 升序索引（默认）
CREATE INDEX idx_users_created ON users (created_at ASC)

-- 降序索引
CREATE INDEX idx_users_created_desc ON users (created_at DESC)
```

## 表达式索引

### 基于函数的索引

```sql
-- 基于函数结果的索引
CREATE INDEX idx_users_lower_email ON users (LOWER(email))

-- 基于连接的索引
CREATE INDEX idx_users_full_name ON users (first_name || ' ' || last_name)
```

## 索引管理

### 查看索引

```sql
-- 列出表的所有索引
SELECT rdb$index_name, rdb$field_name
FROM rdb$indices i
JOIN rdb$index_segments s ON i.rdb$index_name = s.rdb$index_name
WHERE i.rdb$relation_name = 'USERS'
```

### 删除索引

```sql
-- 删除索引
DROP INDEX idx_users_email

-- 如果存在则删除
DROP INDEX IF EXISTS idx_users_email
```

## 索引最佳实践

### 何时创建索引

- WHERE 子句中使用的列
- JOIN 条件中使用的列
- ORDER BY 中使用的列
- 具有高基数的列

### 何时避免索引

- 小表
- 低基数的列
- 频繁更新的列
- 很少在查询中使用的列

## 索引监控

### 检查索引使用情况

```sql
-- 监控索引使用情况
SELECT * FROM mon$records
WHERE mon$record_name = 'INDEX'
```

### 索引统计信息

```sql
-- 获取索引统计信息
SELECT 
    i.rdb$index_name,
    s.rdb$field_name,
    i.rdb$unique_flag
FROM rdb$indices i
JOIN rdb$index_segments s ON i.rdb$index_name = s.rdb$index_name
WHERE i.rdb$relation_name = 'USERS'
```

## 性能考虑

### 索引选择性

```sql
-- 高选择性（适合索引）
SELECT COUNT(DISTINCT email) / COUNT(*) FROM users

-- 低选择性（不适合索引）
SELECT COUNT(DISTINCT gender) / COUNT(*) FROM users
```

### 索引大小

```sql
-- 监控索引大小
SELECT 
    rdb$index_name,
    rdb$segments
FROM rdb$indices
WHERE rdb$relation_name = 'USERS'
```

💡 *AI 提示:* "如何确定 Firebird 中哪些列需要索引？"