# 连接管理

## 概述

Firebird 后端支持连接池，用于高效的资源管理。

## 单连接

### 基本用法

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)
backend.connect()

# 使用连接
try:
    result = backend.execute("SELECT * FROM users")
    # 处理结果
finally:
    backend.disconnect()
```

## 连接池

### 启用池

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,  # 启用池，包含 5 个连接
    pool_timeout=30
)

backend = FirebirdBackend(config=config)
backend.connect()
```

### 池配置

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `pool_size` | int | 0 | 池中的连接数（0 = 禁用） |
| `pool_timeout` | int | 30 | 从池获取连接的超时时间 |
| `pool_recycle` | int | 3600 | 回收连接的秒数 |

### 池使用

```python
# 连接自动管理
backend = FirebirdBackend(config=config)
backend.connect()

# 多个操作使用池连接
for i in range(10):
    result = backend.execute("SELECT * FROM users WHERE id = ?", (i,))
    # 操作后连接返回池中

backend.disconnect()
```

## FastAPI 集成

### 应用程序设置

```python
from fastapi import FastAPI
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

app = FastAPI()

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10
)

backend = FirebirdBackend(config=config)

@app.on_event("startup")
async def startup():
    await backend.connect()

@app.on_event("shutdown")
async def shutdown():
    await backend.disconnect()

@app.get("/users")
async def get_users():
    result = await backend.execute("SELECT * FROM users")
    return result
```

## 连接生命周期

### 连接/断开

```python
# 显式连接管理
backend = FirebirdBackend(config=config)
backend.connect()

# 使用连接
result = backend.execute("SELECT 1 FROM rdb$database")

# 清理
backend.disconnect()
```

### 自动重连

```python
# 后端在连接丢失时处理重连
try:
    backend.execute("SELECT * FROM users")
except ConnectionError:
    # 后端将尝试重连
    backend.execute("SELECT * FROM users")
```

## 最佳实践

### 连接超时

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timeout=30  # 30 秒超时
)
```

### 连接验证

```python
# 使用前测试连接
if backend.is_connected:
    result = backend.execute("SELECT 1 FROM rdb$database")
else:
    backend.connect()
    result = backend.execute("SELECT 1 FROM rdb$database")
```

### 资源清理

```python
# 始终在完成后断开连接
try:
    backend.connect()
    # 使用后端
finally:
    backend.disconnect()
```

💡 *AI 提示:* "如何在多线程应用程序中管理 Firebird 连接？"