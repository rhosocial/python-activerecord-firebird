# 隔离级别

## 概述

Firebird 支持四种事务隔离级别，具有不同的并发和一致性保证。

## 隔离级别

### 读取已提交（默认）

```python
from rhosocial.activerecord.backend.transaction import IsolationLevel

# 只能看到已提交的数据
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)
try:
    # 此处的操作
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

**特性：**
- 只读取已提交的数据
- 可能发生不可重复读
- 可能发生幻读
- 大多数数据库的默认值

### 可重复读取

```python
# 事务内的一致视图
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
try:
    # 所有读取都看到一致的快照
    result1 = backend.execute("SELECT * FROM users WHERE id = 1")
    # 即使另一个事务修改了 users，result1 仍然保持一致
    result2 = backend.execute("SELECT * FROM users WHERE id = 1")
    # result1 == result2
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

**特性：**
- 事务内的一致读取
- 无不可重复读
- 可能发生幻读
- 比 READ COMMITTED 开销更高

### 可序列化

```python
# 最高隔离级别
backend.transaction.begin(isolation_level=IsolationLevel.SERIALIZABLE)
try:
    # 事务完全序列化
    backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
    backend.execute("UPDATE accounts SET balance = balance + 100 WHERE user_id = 2")
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

**特性：**
- 完全序列化的事务
- 无幻读
- 最高开销
- 可能降低并发性

## 选择隔离级别

### 使用 READ COMMITTED 当：

- 主要读取已提交数据
- 可以接受不可重复读
- 性能至关重要

### 使用 REPEATABLE READ 当：

- 需要一致的读取
- 同一数据的多次读取必须相同
- 金融交易

### 使用 SERIALIZABLE 当：

- 需要完全隔离
- 数据一致性至关重要
- 审计跟踪

## Firebird 特定行为

### 事务生命周期

在 Firebird 中，事务隔离受事务生命周期影响：

```python
# 长时间运行的事务可能导致问题
backend.transaction.begin()
# 长时间操作...
backend.transaction.commit()

# 更好：使用更短的事务
backend.transaction.begin()
# 快速操作
backend.transaction.commit()
```

### 记录版本控制

Firebird 使用带记录版本控制的 MVCC：

```python
# 每个事务看到自己的快照
backend.transaction.begin()
result = backend.execute("SELECT * FROM users")
# 结果基于事务开始时间
backend.transaction.commit()
```

## Python 示例

### 读取已提交示例

```python
def read_committed_example(backend):
    # 事务 1
    backend.transaction.begin()
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    # 对其他事务不可见
    
    # 事务 2（并发）
    backend.transaction.begin()
    result = backend.execute("SELECT * FROM users")
    # Alice 不可见（未提交）
    backend.transaction.commit()
    
    # 提交事务 1
    backend.transaction.commit()
    
    # 事务 3
    backend.transaction.begin()
    result = backend.execute("SELECT * FROM users")
    # Alice 可见（已提交）
    backend.transaction.commit()
```

### 可重复读取示例

```python
def repeatable_read_example(backend):
    backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
    
    # 第一次读取
    result1 = backend.execute("SELECT * FROM users WHERE id = 1")
    
    # 另一个事务更新该行
    # （这将是单独的后端实例）
    
    # 第二次读取 - 相同结果
    result2 = backend.execute("SELECT * FROM users WHERE id = 1")
    assert result1 == result2
    
    backend.transaction.commit()
```

## 最佳实践

### 保持事务简短

```python
# 好：简短事务
backend.transaction.begin()
backend.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = 1")
backend.transaction.commit()

# 不好：长事务
backend.transaction.begin()
# 长时间操作...
backend.transaction.commit()
```

### 选择适当的隔离级别

```python
# 对于只读报告
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)

# 对于金融交易
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)

# 对于关键一致性
backend.transaction.begin(isolation_level=IsolationLevel.SERIALIZABLE)
```

💡 *AI 提示:* "我的应用程序何时应使用 REPEATABLE READ 而不是 READ COMMITTED？"