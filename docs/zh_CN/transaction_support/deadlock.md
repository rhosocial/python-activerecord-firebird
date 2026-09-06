# 死锁处理

## 概述

Firebird 自动检测死锁并引发错误代码。后端提供处理和重试事务的机制。

## 死锁检测

### Firebird 错误代码

| 错误代码 | 描述 |
|----------|------|
| 335544336 | 锁冲突 (isc_lock_conflict) |
| 335544349 | 外键违规 |
| 335544350 | 主键违规 |

### 处理死锁

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

## 重试策略

### 简单重试

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
                time.sleep(delay)
            else:
                raise
    return False
```

### 指数退避

```python
import time
from rhosocial.activerecord.backend import errors as exc

def execute_with_exponential_backoff(backend, max_retries=3, base_delay=0.1):
    for attempt in range(max_retries):
        try:
            backend.transaction.begin()
            # 执行操作
            backend.transaction.commit()
            return True
        except exc.LockConflictError:
            backend.transaction.rollback()
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise
    return False
```

### 随机退避

```python
import time
import random
from rhosocial.activerecord.backend import errors as exc

def execute_with_randomized_backoff(backend, max_retries=3, base_delay=0.1):
    for attempt in range(max_retries):
        try:
            backend.transaction.begin()
            # 执行操作
            backend.transaction.commit()
            return True
        except exc.LockConflictError:
            backend.transaction.rollback()
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                time.sleep(delay)
            else:
                raise
    return False
```

## 预防策略

### 短事务

```python
# 好：简短事务
backend.transaction.begin()
backend.execute("UPDATE accounts SET balance = balance - 100 WHERE user_id = 1")
backend.transaction.commit()

# 不好：长事务
backend.transaction.begin()
# 长时间操作...
backend.transaction.commit()
```

### 一致的锁顺序

```python
# 好：一致的顺序
def transfer_funds(backend, from_id, to_id, amount):
    backend.transaction.begin()
    try:
        # 始终按相同顺序锁定
        if from_id < to_id:
            backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
            backend.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
        else:
            backend.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
            backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise

# 不好：不一致的顺序
def bad_transfer(backend, from_id, to_id, amount):
    backend.transaction.begin()
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
    backend.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))
    backend.transaction.commit()
```

### 使用较低的隔离级别

```python
# 尽可能使用 READ COMMITTED
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)
try:
    # 操作
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## 高级模式

### 断路器

```python
import time
from rhosocial.activerecord.backend import errors as exc

class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise Exception("断路器已打开")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            raise

# 使用
circuit_breaker = CircuitBreaker()

def safe_operation():
    return circuit_breaker.call(
        lambda: backend.execute("SELECT 1 FROM rdb$database")
    )
```

### 死锁检测

```python
import time
from rhosocial.activerecord.backend import errors as exc

def detect_deadlock(backend, operation, timeout=5):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            return operation()
        except exc.LockConflictError:
            if time.time() - start_time >= timeout:
                raise
            time.sleep(0.1)
    raise Exception("死锁超时超过")
```

## 监控

### 记录死锁

```python
import logging
from rhosocial.activerecord.backend import errors as exc

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def log_deadlocks(backend, operation):
    try:
        return operation()
    except exc.LockConflictError as e:
        logger.warning(f"检测到死锁: {e}")
        raise
```

### 统计信息

```python
class DeadlockStats:
    def __init__(self):
        self.total_attempts = 0
        self.deadlocks = 0
        self.successful = 0
    
    def record_attempt(self):
        self.total_attempts += 1
    
    def record_deadlock(self):
        self.deadlocks += 1
    
    def record_success(self):
        self.successful += 1
    
    def get_stats(self):
        return {
            'total_attempts': self.total_attempts,
            'deadlocks': self.deadlocks,
            'successful': self.successful,
            'deadlock_rate': self.deadlocks / self.total_attempts if self.total_attempts > 0 else 0
        }
```

## 最佳实践

### 保持事务简短

```python
# 好
backend.transaction.begin()
backend.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = 1")
backend.transaction.commit()

# 不好
backend.transaction.begin()
# 长时间处理...
backend.transaction.commit()
```

### 使用适当的隔离级别

```python
# 尽可能使用 READ COMMITTED
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)

# 需要时使用 REPEATABLE READ
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
```

### 实现重试逻辑

```python
def robust_operation(backend, operation):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return operation()
        except exc.LockConflictError:
            if attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))
            else:
                raise
```

💡 *AI 提示:* "如何为 Firebird 死锁实现重试逻辑？"