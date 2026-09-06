# Firebird 特定功能

## 概述

Firebird 提供 several 独特功能，使其与其他数据库区分开来。本节介绍 Firebird 特定的数据类型、SQL 方言扩展和特殊功能。

## 字段类型

### BLOB 类型

Firebird 支持多种 BLOB 子类型，用于不同的数据存储需求：

```python
from rhosocial.activerecord.backend.impl.firebird.types import FirebirdBlobType

# 二进制 BLOB (SUB_TYPE 0)
binary_blob = FirebirdBlobType(sub_type=0, segment_size=16384)

# 文本 BLOB (SUB_TYPE 1)
text_blob = FirebirdBlobType(sub_type=1, segment_size=16384, character_set='UTF8')
```

### 数组类型

Firebird 支持多维数组：

```python
from rhosocial.activerecord.backend.impl.firebird.types import FirebirdArrayType

# 一维整数数组
arr = FirebirdArrayType(base_type='INTEGER', dimensions=[5])

# 二维字符串数组
arr = FirebirdArrayType('VARCHAR(30)', dimensions=[3, 4])
```

### 域类型

可重用的列类型定义：

```python
from rhosocial.activerecord.backend.impl.firebird.types import FirebirdDomainType

# 创建电子邮件地址域
email_domain = FirebirdDomainType(
    'VARCHAR(255)',
    not_null=True,
    check="VALUE LIKE '%@%.%'"
)
```

## 方言表达式

### EXECUTE BLOCK

Firebird 支持用于复杂操作的匿名 PSQL 块：

```python
# 在单个块中执行多个语句
backend.execute("""
    EXECUTE BLOCK AS
    BEGIN
        INSERT INTO audit_log (action, timestamp) VALUES ('LOGIN', CURRENT_TIMESTAMP);
        UPDATE user_stats SET login_count = login_count + 1 WHERE user_id = 1;
    END
""")
```

### RETURNING 子句

Firebird 支持 INSERT、UPDATE 和 DELETE 的 RETURNING：

```python
# 带 RETURNING 的 INSERT
result = backend.execute(
    "INSERT INTO users (name, email) VALUES (?, ?) RETURNING id",
    ("Alice", "alice@example.com")
)

# 带 RETURNING 的 UPDATE
result = backend.execute(
    "UPDATE users SET name = ? WHERE id = ? RETURNING name, email",
    ("Alice Smith", 1)
)
```

### MERGE 语句

Firebird 2.1+ 支持用于更新插入操作的 MERGE：

```python
backend.execute("""
    MERGE INTO target_table t
    USING source_table s ON t.id = s.id
    WHEN MATCHED THEN
        UPDATE SET t.name = s.name, t.value = s.value
    WHEN NOT MATCHED THEN
        INSERT (id, name, value) VALUES (s.id, s.name, s.value)
""")
```

### 窗口函数

Firebird 3.0+ 支持窗口函数：

```python
backend.execute("""
    SELECT 
        name,
        department,
        salary,
        ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
    FROM employees
""")
```

## 索引

### 标准索引

```python
# 创建标准索引
backend.execute("CREATE INDEX idx_users_email ON users (email)")

# 创建唯一索引
backend.execute("CREATE UNIQUE INDEX idx_users_username ON users (username)")
```

### 表达式索引

Firebird 支持基于表达式的索引：

```python
# 基于表达式的索引
backend.execute("CREATE INDEX idx_users_lower_email ON users (LOWER(email))")
```

## EXPLAIN

### 查询执行计划

Firebird 提供 EXPLAIN 用于查询分析：

```python
# 获取执行计划
result = backend.execute("EXPLAIN SELECT * FROM users WHERE email = 'alice@example.com'")
print(result)
```

## 内省

### 数据库元数据

```python
# 列出所有表
tables = backend.introspect.tables()

# 获取表列
columns = backend.introspect.columns("users")

# 获取表索引
indexes = backend.introspect.indexes("users")
```

## EXECUTE BLOCK

### 匿名 PSQL 块

EXECUTE BLOCK 允许将多个语句作为单个单元执行：

```python
# 复杂数据操作
backend.execute("""
    EXECUTE BLOCK AS
    DECLARE variable total DECIMAL(10,2);
    BEGIN
        SELECT SUM(amount) INTO total FROM orders WHERE user_id = CURRENT_USER_ID;
        INSERT INTO user_reports (user_id, total_orders, report_date)
        VALUES (CURRENT_USER_ID, total, CURRENT_DATE);
    END
""")
```

### EXECUTE BLOCK 中的动态 SQL

```python
# 带输入参数的动态 SQL
backend.execute("""
    EXECUTE BLOCK (user_id INTEGER = ?) AS
    BEGIN
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
        INSERT INTO login_history (user_id, login_time) VALUES (:user_id, CURRENT_TIMESTAMP);
    END
""", (1,))
```

💡 *AI 提示:* "何时应使用 EXECUTE BLOCK 而不是多个单独的查询？"