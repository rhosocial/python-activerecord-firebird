# 并行工作器

## 概述

本节介绍 Firebird 特定的并发特性和并行处理模式。

## Firebird 并发特性

### 多版本并发控制 (MVCC)

Firebird 使用 MVCC，提供：

- **读取者不阻塞写入者**: SELECT 查询不锁定行
- **写入者不阻塞读取者**: INSERT/UPDATE/DELETE 不阻塞 SELECT
- **快照隔离**: 每个事务看到一致的快照

### 事务生命周期

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

## 并发访问模式

### 读取密集型工作负载

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from concurrent.futures import ThreadPoolExecutor
import threading

def read_worker(backend, user_id):
    """读取操作的工作器。"""
    result = backend.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return result

def parallel_reads(backend, user_ids):
    """执行并行读取。"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(read_worker, backend, uid) for uid in user_ids]
        return [f.result() for f in futures]

# 使用
user_ids = [1, 2, 3, 4, 5]
results = parallel_reads(backend, user_ids)
```

### 写入密集型工作负载

```python
def write_worker(backend, data):
    """写入操作的工作器。"""
    backend.transaction.begin()
    try:
        backend.execute(
            "INSERT INTO logs (message, timestamp) VALUES (?, ?)",
            (data['message'], data['timestamp'])
        )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

def parallel_writes(backend, data_list):
    """使用适当的事务隔离执行并行写入。"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(write_worker, backend, data) for data in data_list]
        return [f.result() for f in futures]
```

## 工作器的连接池

### 配置池

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

# 为并发访问配置连接池
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10,  # 每个工作器一个连接
    pool_timeout=30
)

backend = FirebirdBackend(config=config)
backend.connect()

# 工作器将共享连接池
```

### 池监控

```python
def monitor_pool(backend):
    """监控连接池使用情况。"""
    print(f"已连接: {backend.is_connected}")
    print(f"池大小: {backend.config.pool_size}")
```

## FastAPI 集成

### 异步工作器

```python
from fastapi import FastAPI, Depends
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

app = FastAPI()

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)

@app.on_event("startup")
async def startup():
    await backend.connect()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    result = await backend.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    return result

@app.post("/users")
async def create_user(name: str, email: str):
    await backend.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        (name, email)
    )
    return {"status": "created"}
```

## 批量处理

### 批量插入

```python
def bulk_insert(backend, table, data_list):
    """高效插入多行。"""
    backend.transaction.begin()
    try:
        for data in data_list:
            backend.execute(
                f"INSERT INTO {table} (name, value) VALUES (?, ?)",
                (data['name'], data['value'])
            )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

# 使用
data = [
    {"name": f"item_{i}", "value": i * 10}
    for i in range(1000)
]
bulk_insert(backend, "products", data)
```

### 批量更新

```python
def bulk_update(backend, table, updates):
    """高效更新多行。"""
    backend.transaction.begin()
    try:
        for update in updates:
            backend.execute(
                f"UPDATE {table} SET value = ? WHERE id = ?",
                (update['value'], update['id'])
            )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

# 使用
updates = [
    {"id": i, "value": f"updated_{i}"}
    for i in range(1, 101)
]
bulk_update(backend, "products", updates)
```

## 最佳实践

### 使用连接池

```python
# 并发访问时始终使用连接池
config = FirebirdConnectionConfig(
    pool_size=10,
    pool_timeout=30
)
```

### 保持事务简短

```python
# 好：简短事务
backend.transaction.begin()
backend.execute("INSERT INTO logs (message) VALUES (?)", ("test",))
backend.transaction.commit()

# 不好：长事务
backend.transaction.begin()
# 长时间处理...
backend.transaction.commit()
```

### 优雅地处理错误

```python
def safe_worker(backend, data):
    """带错误处理的工作器。"""
    try:
        backend.transaction.begin()
        backend.execute(
            "INSERT INTO logs (message) VALUES (?)",
            (data['message'],)
        )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        print(f"错误: {e}")
```

### 监控性能

```python
import time

def monitor_performance(backend, operations):
    """监控操作性能。"""
    start_time = time.time()
    for op in operations:
        op()
    end_time = time.time()
    print(f"总时间: {end_time - start_time:.2f}s")
```

## 常见模式

### 工作器池

```python
from concurrent.futures import ThreadPoolExecutor
import threading

class WorkerPool:
    def __init__(self, backend, num_workers=5):
        self.backend = backend
        self.num_workers = num_workers
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
    
    def submit(self, func, *args, **kwargs):
        return self.executor.submit(func, *args, **kwargs)
    
    def shutdown(self):
        self.executor.shutdown()
```

### 生产者-消费者

```python
import queue
import threading

def producer(backend, data_queue):
    """生产者线程。"""
    for i in range(100):
        data_queue.put({"id": i, "value": f"item_{i}"})

def consumer(backend, data_queue):
    """消费者线程。"""
    while True:
        try:
            data = data_queue.get(timeout=1)
            backend.execute(
                "INSERT INTO products (id, value) VALUES (?, ?)",
                (data['id'], data['value'])
            )
        except queue.Empty:
            break
```

💡 *AI 提示:* "如何使用 Firebird 实现并发处理？"