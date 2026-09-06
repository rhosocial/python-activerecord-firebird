# 内省

## 概述

Firebird 提供元数据查询，用于检查数据库模式和结构。

## 列出表

### 系统目录

```sql
-- 列出所有用户表
SELECT rdb$relation_name
FROM rdb$relations
WHERE rdb$system_flag = 0
ORDER BY rdb$relation_name
```

### 使用 INFORMATION_SCHEMA

```sql
-- 列出表 (Firebird 3.0+)
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'CURRENT_USER'
ORDER BY table_name
```

## 表结构

### 列信息

```sql
-- 获取表的列详细信息
SELECT 
    rf.rdb$field_name,
    f.rdb$field_type,
    f.rdb$field_length,
    f.rdb$field_sub_type,
    rf.rdb$default_value
FROM rdb$relation_fields rf
JOIN rdb$fields f ON rf.rdb$field_source = f.rdb$field_name
WHERE rf.rdb$relation_name = 'USERS'
ORDER BY rf.rdb$field_position
```

### 字段类型

```sql
-- 获取字段类型名称
SELECT 
    rf.rdb$field_name,
    CASE f.rdb$field_type
        WHEN 7 THEN 'SMALLINT'
        WHEN 8 THEN 'INTEGER'
        WHEN 10 THEN 'FLOAT'
        WHEN 12 THEN 'DATE'
        WHEN 13 THEN 'TIME'
        WHEN 14 THEN 'CHAR'
        WHEN 16 THEN 'BIGINT'
        WHEN 27 THEN 'DOUBLE'
        WHEN 35 THEN 'TIMESTAMP'
        WHEN 37 THEN 'VARCHAR'
        WHEN 261 THEN 'BLOB'
        ELSE 'UNKNOWN'
    END as field_type_name
FROM rdb$relation_fields rf
JOIN rdb$fields f ON rf.rdb$field_source = f.rdb$field_name
WHERE rf.rdb$relation_name = 'USERS'
ORDER BY rf.rdb$field_position
```

## 索引信息

### 列出索引

```sql
-- 获取表的索引
SELECT 
    i.rdb$index_name,
    s.rdb$field_name,
    i.rdb$unique_flag
FROM rdb$indices i
JOIN rdb$index_segments s ON i.rdb$index_name = s.rdb$index_name
WHERE i.rdb$relation_name = 'USERS'
ORDER BY i.rdb$index_name
```

### 索引详细信息

```sql
-- 获取索引详细信息
SELECT 
    i.rdb$index_name,
    i.rdb$relation_name,
    i.rdb$unique_flag,
    i.rdb$index_type
FROM rdb$indices i
WHERE i.rdb$relation_name = 'USERS'
```

## 外键

### 列出外键

```sql
-- 获取表的外键
SELECT 
    rc.rdb$constraint_name,
    rc.rdb$constraint_type,
    rc.rdb$table_name,
    rc.rdb$constraint_name
FROM rdb$relation_constraints rc
WHERE rc.rdb$relation_name = 'USERS'
AND rc.rdb$constraint_type = 'FOREIGN KEY'
```

### 外键详细信息

```sql
-- 获取外键列映射
SELECT 
    rc.rdb$constraint_name,
    s1.rdb$field_name as source_column,
    s2.rdb$field_name as referenced_column,
    rc.rdb$relation_name as referenced_table
FROM rdb$relation_constraints rc
JOIN rdb$index_segments s1 ON rc.rdb$index_name = s1.rdb$index_name
JOIN rdb$ref_constraints refc ON rc.rdb$constraint_name = refc.rdb$constraint_name
JOIN rdb$relation_constraints rc2 ON refc.rdb$const_name_uq = rc2.rdb$constraint_name
JOIN rdb$index_segments s2 ON rc2.rdb$index_name = s2.rdb$index_name
WHERE rc.rdb$relation_name = 'USERS'
```

## 视图

### 列出视图

```sql
-- 列出所有视图
SELECT rdb$relation_name
FROM rdb$relations
WHERE rdb$relation_type = 1  -- 1 = 视图
AND rdb$system_flag = 0
ORDER BY rdb$relation_name
```

### 视图定义

```sql
-- 获取视图源
SELECT rdb$view_source
FROM rdb$relations
WHERE rdb$relation_name = 'ACTIVE_USERS'
```

## 存储过程

### 列出过程

```sql
-- 列出所有存储过程
SELECT rdb$procedure_name
FROM rdb$procedures
WHERE rdb$system_flag = 0
ORDER BY rdb$procedure_name
```

### 过程参数

```sql
-- 获取过程参数
SELECT 
    p.rdb$parameter_name,
    p.rdb$parameter_type,  -- 0 = 输入，1 = 输出
    f.rdb$field_type,
    f.rdb$field_length
FROM rdb$procedure_parameters p
JOIN rdb$fields f ON p.rdb$field_source = f.rdb$field_name
WHERE p.rdb$procedure_name = 'GET_USER_STATS'
ORDER BY p.rdb$parameter_number
```

## 触发器

### 列出触发器

```sql
-- 列出所有触发器
SELECT rdb$trigger_name
FROM rdb$triggers
WHERE rdb$system_flag = 0
ORDER BY rdb$trigger_name
```

### 触发器详细信息

```sql
-- 获取触发器详细信息
SELECT 
    rdb$trigger_name,
    rdb$relation_name,
    rdb$trigger_type,  -- 1 = 之前，2 = 之后
    rdb$trigger_inactive
FROM rdb$triggers
WHERE rdb$relation_name = 'USERS'
```

## 生成器（序列）

### 列出生成器

```sql
-- 列出所有生成器
SELECT rdb$generator_name
FROM rdb$generators
WHERE rdb$system_flag = 0
ORDER BY rdb$generator_name
```

### 生成器值

```sql
-- 获取当前生成器值
SELECT GEN_ID(generator_name, 0) FROM rdb$database
```

## Python 内省

### 使用后端

```python
# 列出表
tables = backend.introspect.tables()

# 获取表列
columns = backend.introspect.columns("users")

# 获取表索引
indexes = backend.introspect.indexes("users")

# 获取外键
fk = backend.introspect.foreign_keys("users")
```

### 自定义内省查询

```python
# 执行自定义元数据查询
result = backend.execute("""
    SELECT rdb$relation_name
    FROM rdb$relations
    WHERE rdb$system_flag = 0
    ORDER BY rdb$relation_name
""")
tables = [row[0] for row in result]
```

💡 *AI 提示:* "如何列出 Firebird 表的所有列及其数据类型？"