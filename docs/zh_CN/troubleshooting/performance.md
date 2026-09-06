# 性能问题

## 概述

本节介绍 Firebird 数据库的性能分析和优化。

## 慢查询分析

### 启用查询日志

```python
import logging

# 启用查询日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('rhosocial.activerecord')
logger.setLevel(logging.DEBUG)
```

### 使用 EXPLAIN

```python
# 分析查询执行计划
result = backend.execute("""
    EXPLAIN SELECT * FROM users 
    WHERE email LIKE '%@example.com%' 
    ORDER BY created_at DESC
""")
print(result)
```

### 分析查询

```python
import time

def profile_query(backend, query, params=None):
    """分析查询执行时间。"""
    start_time = time.time()
    result = backend.execute(query, params)
    end_time = time.time()
    print(f"查询时间: {(end_time - start_time) * 1000:.2f}ms")
    return result
```

## 常见性能问题

### 缺少索引

```python
# 检查缺少的索引
result = backend.execute("""
    SELECT rdb$relation_name, rdb$field_name
    FROM rdb$relation_fields
    WHERE rdb$relation_name = 'USERS'
    ORDER BY rdb$field_position
""")

# 创建适当的索引
backend.execute("CREATE INDEX idx_users_email ON users (email)")
backend.execute("CREATE INDEX idx_users_created_at ON users (created_at)")
```

### 大结果集

```python
# 对大结果集使用分页
def get_users_page(backend, page=1, per_page=100):
    offset = (page - 1) * per_page
    return backend.execute("""
        SELECT * FROM users 
        ORDER BY id 
        ROWS ? TO ?
    """, (offset + 1, offset + per_page))
```

### 连接池耗尽

```python
# 监控连接池
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10,  # 增加池大小
    pool_timeout=60  # 增加超时时间
)
```

### 锁冲突

```python
# 检测锁冲突
from rhosocial.activerecord.backend import errors as exc

try:
    backend.transaction.begin()
    # 长时间运行的操作
    backend.transaction.commit()
except exc.LockConflictError as e:
    print(f"检测到锁冲突: {e}")
    backend.transaction.rollback()
```

## 优化策略

### 使用适当的隔离级别

```python
# 大多数情况使用 READ COMMITTED
backend.transaction.begin(isolation_level=IsolationLevel.READ_COMMITTED)

# 需要时使用 REPEATABLE READ
backend.transaction.begin(isolation_level=IsolationLevel.REPEATABLE_READ)
```

### 保持事务简短

```python
# 好：简短事务
backend.transaction.begin()
backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (100, 1))
backend.transaction.commit()

# 不好：长事务
backend.transaction.begin()
# 长时间处理...
backend.transaction.commit()
```

### 使用批量操作

```python
# 好：批量插入
def bulk_insert(backend, table, data_list):
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

# 不好：单个插入
for data in data_list:
    backend.execute("INSERT INTO table (name) VALUES (?)", (data['name'],))
```

### 优化查询

```python
# 好：特定列
backend.execute("SELECT id, name, email FROM users WHERE active = 1")

# 不好：SELECT *
backend.execute("SELECT * FROM users WHERE active = 1")
```

## 监控

### 查询统计

```python
def get_query_stats(backend):
    """获取查询统计信息。"""
    result = backend.execute("""
        SELECT 
            rdb$relation_name,
            rdb$field_name
        FROM rdb$relation_fields
        WHERE rdb$relation_name = 'USERS'
    """)
    return result
```

### 连接统计

```python
def get_connection_stats(backend):
    """获取连接统计信息。"""
    return {
        'is_connected': backend.is_connected,
        'pool_size': backend.config.pool_size,
        'pool_timeout': backend.config.pool_timeout
    }
```

## 性能调优

### 数据库配置

```sql
-- 优化 Firebird 配置
-- 编辑 firebird.conf
```

### 索引优化

```sql
-- 创建覆盖索引
CREATE INDEX idx_users_email_name ON users (email) INCLUDE (name)

-- 删除未使用的索引
DROP INDEX idx_unused_index
```

### 查询优化

```python
# 使用 EXPLAIN 分析查询
result = backend.execute("EXPLAIN SELECT * FROM users WHERE email = ?", ('test@example.com',))
print(result)
```

## 最佳实践

### 监控性能

```python
# 定期性能检查
def performance_check(backend):
    # 检查慢查询
    result = backend.execute("EXPLAIN SELECT * FROM users")
    print(f"查询计划: {result}")
    
    # 检查索引使用情况
    result = backend.execute("""
        SELECT rdb$index_name
        FROM rdb$indices
        WHERE rdb$relation_name = 'USERS'
    """)
    print(f"索引: {result}")
```

### 定期优化

```python
# 定期优化
def optimize_database(backend):
    # 分析表
    backend.execute("ANALYZE users")
    
    # 重建索引
    backend.execute("REBUILD INDEX idx_users_email")
```

### 使用连接池

```python
# 始终使用连接池
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)
```

💡 *AI 提示:* "如何优化 Firebird 查询以获得更好的性能？"