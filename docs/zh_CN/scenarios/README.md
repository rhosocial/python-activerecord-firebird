# 场景

## 概述

本节介绍 Firebird 后端的常见使用场景和模式，包括并发特性和最佳实践。

## 并行工作器

### Firebird 并发特性

Firebird 使用多版本并发控制 (MVCC)，提供：

- **读取者不阻塞写入者**: SELECT 查询不锁定行
- **写入者不阻塞读取者**: INSERT/UPDATE/DELETE 不阻塞 SELECT
- **快照隔离**: 每个事务看到一致的快照

### 并发访问模式

#### 读取密集型工作负载

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

#### 写入密集型工作负载

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

### 工作器的连接池

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

### FastAPI 与 Firebird

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

## 数据迁移

### 在表之间迁移数据

```python
def migrate_data(backend, source_table, target_table, transform_func):
    """从源表迁移数据到目标表。"""
    # 读取源数据
    source_data = backend.execute(f"SELECT * FROM {source_table}")
    
    # 转换并插入
    backend.transaction.begin()
    try:
        for row in source_data:
            transformed = transform_func(row)
            backend.execute(
                f"INSERT INTO {target_table} (col1, col2) VALUES (?, ?)",
                (transformed['col1'], transformed['col2'])
            )
        backend.transaction.commit()
    except Exception as e:
        backend.transaction.rollback()
        raise

# 使用
def transform_user(row):
    return {
        'col1': row[1].upper(),  # name 转为大写
        'col2': row[2]           # email 不变
    }

migrate_data(backend, "users_old", "users_new", transform_user)
```

## 报告和分析

### 复杂聚合查询

```python
def get_sales_report(backend, start_date, end_date):
    """生成带聚合的销售报告。"""
    return backend.execute("""
        SELECT 
            product_name,
            SUM(quantity) as total_quantity,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM sales
        WHERE sale_date BETWEEN ? AND ?
        GROUP BY product_name
        ORDER BY total_amount DESC
    """, (start_date, end_date))

# 使用
report = get_sales_report(backend, "2026-01-01", "2026-12-31")
```

### 用于分析的窗口函数

```python
def get_ranked_products(backend):
    """使用窗口函数获取按销售排名的产品。"""
    return backend.execute("""
        SELECT 
            product_name,
            total_sales,
            RANK() OVER (ORDER BY total_sales DESC) as sales_rank,
            PERCENT_RANK() OVER (ORDER BY total_sales DESC) as percentile
        FROM (
            SELECT 
                product_name,
                SUM(amount) as total_sales
            FROM sales
            GROUP BY product_name
        ) ranked
        ORDER BY sales_rank
    """)
```

## 错误恢复模式

### 指数退避重试

```python
import time
from rhosocial.activerecord.backend import errors as exc

def execute_with_retry(backend, operation, max_retries=3, base_delay=0.1):
    """使用重试逻辑执行操作。"""
    for attempt in range(max_retries):
        try:
            return operation()
        except exc.LockConflictError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise

# 使用
def insert_operation():
    backend.transaction.begin()
    try:
        backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise

execute_with_retry(backend, insert_operation)
```

### 断路器模式

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

💡 *AI 提示:* "如何使用 Firebird 实现幂等操作？"