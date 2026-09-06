# 字符集/编码

## 概述

Firebird 支持多种字符集，用于数据存储和检索。

## 配置

### 设置字符集

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8"  # 默认字符集
)
```

### 常见字符集

| 字符集 | 描述 |
|--------|------|
| `UTF8` | Unicode UTF-8（推荐） |
| `ISO8859_1` | Latin-1 |
| `WIN1252` | Windows Latin-1 |
| `ASCII` | ASCII |
| `UNICODE_FSS` | Unicode 分数空间填充 |

## 字符集操作

### 带字符集的查询

```sql
-- 在查询中指定字符集
SELECT * FROM users WHERE name = 'Alice' CHARACTER SET UTF8
```

### 列字符集

```sql
-- 创建带字符集的表
CREATE TABLE users (
    id INTEGER,
    name VARCHAR(100) CHARACTER SET UTF8,
    email VARCHAR(255) CHARACTER SET UTF8
)
```

### BLOB 字符集

```sql
-- 带字符集的文本 BLOB
CREATE TABLE documents (
    id INTEGER,
    content BLOB SUB_TYPE TEXT SEGMENT SIZE 16384 CHARACTER SET UTF8
)
```

## 字符集转换

### 自动转换

后端自动处理字符集转换：

```python
# 数据在 Python 字符串和 Firebird 字符集之间转换
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
result = backend.execute("SELECT name FROM users WHERE id = 1")
# result[0][0] 是 Python 字符串
```

### 手动转换

```python
# 显式字符集转换
backend.execute("""
    INSERT INTO users (name) 
    VALUES (? CHARACTER SET UTF8)
""", ("Alice",))
```

## 最佳实践

### 使用 UTF-8

```python
# 推荐：使用 UTF-8 以获得最大兼容性
config = FirebirdConnectionConfig(
    charset="UTF8"
)
```

### 一致的字符集

```python
# 确保应用程序中字符集一致
config = FirebirdConnectionConfig(
    charset="UTF8"
)

# 所有操作使用相同的字符集
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
```

### 字符集验证

```python
# 验证字符集支持
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("测试",))
except Exception as e:
    print(f"字符集错误: {e}")
```

## 故障排除

### 常见字符集问题

1. **数据截断**
   - 检查列长度
   - 验证字符集支持数据

2. **转换错误**
   - 确保客户端和服务器使用兼容的字符集
   - 检查无效字符

3. **显示问题**
   - 验证终端支持字符集
   - 检查字体支持

### 错误消息

```
Invalid character set
```

**解决方案**: 检查字符集是否受 Firebird 支持。

```
Character set conversion error
```

**解决方案**: 确保源和目标字符集兼容。

💡 *AI 提示:* "如何在 Firebird 中处理国际字符？"