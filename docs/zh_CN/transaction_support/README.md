# 事务支持

## 概述

Firebird 提供强大的事务支持，具有多个隔离级别和保存点功能。Firebird 后端实现了利用 Firebird 原生事务 API 的事务管理器。

## 事务管理器 API

### 基本事务用法

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

backend = FirebirdBackend(config=config)
backend.connect()

# 开始事务
backend.transaction.begin()

try:
    # 执行操作
    backend.execute("INSERT INTO users (name, email) VALUES (?, ?)", 
                    ("Alice", "alice@example.com"))
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", 
                    (100, 1))
    
    # 提交事务
    backend.transaction.commit()
except Exception as e:
    # 出错时回滚
    backend.transaction.rollback()
    raise
```

### 上下文管理器

```python
# 使用上下文管理器自动提交/回滚
with backend.transaction:
    backend.execute("INSERT INTO users (name, email) VALUES (?, ?)", 
                    ("Alice", "alice@example.com"))
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE user_id = ?", 
                    (100, 1))
# 如果没有异常则自动提交，如果有异常则自动回滚
```

## 隔离级别

Firebird 支持四种隔离级别：

### 读取已提交（默认）

```python
from rhosocial.activerecord.backend.transaction import IsolationLevel

# 读取已提交 - 只能看到已提交的数据
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)
try:
    # 此处的操作
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### 可重复读取

```python
# 可重复读取 - 事务内的一致视图
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

### 可序列化

```python
# 可序列化 - 最高隔离级别
backend.transaction.begin(isolation_level=IsolationLevel.SERIALIZABLE)
try:
    # 事务完全序列化
    backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
    backend.execute("UPDATE accounts SET balance = balance + 100 WHERE user_id = 2")
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## 保存点

### 创建保存点

```python
# 创建保存点
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # 创建保存点
    backend.transaction.savepoint("after_insert")
    
    backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
    
    # 如果需要，回滚到保存点
    backend.transaction.rollback_savepoint("after_insert")
    
    # 只有 Alice 保留，订单被回滚
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### 使用保存点的嵌套事务

```python
# 模拟嵌套事务
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # 为嵌套操作创建保存点
    backend.transaction.savepoint("nested")
    try:
        backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
        backend.transaction.release_savepoint("nested")
    except:
        backend.transaction.rollback_savepoint("nested")
        # 继续外部事务
    
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## 死锁处理

### Firebird 死锁检测

Firebird 自动检测死锁并引发错误代码 335544336 (isc_lock_conflict)。

```python
from rhosocial.activerecord.backend import errors as exc

try:
    backend.transaction.begin()
    backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
    backend.transaction.commit()
except exc.LockConflictError as e:
    # 处理死锁
    backend.transaction.rollback()
    # 此处的重试逻辑
except exc.DatabaseError as e:
    if "lock conflict" in str(e).lower():
        # 处理锁冲突
        backend.transaction.rollback()
```

### 重试策略

```python
import time
from rhosocial.activerecord.backend import errors as exc

def execute_with_retry(backend, max_retries=3, delay=0.1):
    for attempt in range(max_retries):
        try:
            backend.transaction.begin()
            # 执行操作
            backend.transaction.commit()
            return True
        except exc.LockConflictError:
            backend.transaction.rollback()
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # 指数退避
            else:
                raise
    return False
```

## 事务模式

### 只读事务

```python
# 用于报告的只读事务
backend.transaction.begin(mode="read_only")
try:
    result = backend.execute("SELECT * FROM large_table")
    # 处理结果
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### 读写事务

```python
# 读写事务（默认）
backend.transaction.begin(mode="read_write")
try:
    backend.execute("INSERT INTO audit_log (action) VALUES (?)", ("login",))
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

💡 *AI 提示:* "我的应用程序何时应使用 REPEATABLE READ 而不是 READ COMMITTED？"