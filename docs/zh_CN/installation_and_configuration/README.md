# 安装与配置

## 安装指南

### 先决条件

- Python 3.11 或更高版本（包括 3.13t/3.14t 自由线程构建）
- Firebird 数据库服务器（建议 3.0 或更高版本）
- `firebird-driver` Python 包

### 安装

使用 pip 安装 Firebird 后端：

```bash
pip install rhosocial-activerecord-firebird
```

这将安装：
- `rhosocial-activerecord-firebird` 包
- `firebird-driver` 依赖项
- `rhosocial-activerecord` 核心库

### 可选依赖项

对于连接池，请使用 pooling 额外选项安装：

```bash
pip install rhosocial-activerecord-firebird[pooling]
```

这将添加 `DBUtils` 以支持连接池。

### 开发安装

用于开发或测试：

```bash
pip install rhosocial-activerecord-firebird[dev,test]
```

## 连接配置

### 基本配置

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/3.0/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)
backend.connect()
```

### 配置选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `host` | str | `"localhost"` | Firebird 服务器主机名 |
| `port` | int | `3050` | Firebird 服务器端口 |
| `database` | str | None | 数据库路径或 host:path 连接字符串 |
| `username` | str | None | 数据库用户名 |
| `password` | str | None | 数据库密码 |
| `role` | str | None | SQL 角色名称 |
| `charset` | str | `"UTF8"` | 连接字符集 |
| `page_size` | int | None | 数据库页面大小 |
| `wire_compression` | bool | `False` | 启用线路压缩 |
| `use_unicode` | bool | `True` | 使用 Unicode 字符串 |
| `autocommit` | bool | `False` | 启用自动提交模式 |
| `timeout` | int | None | 连接超时（秒） |

### 环境变量

您可以使用 `FIREBIRD_` 前缀的环境变量配置后端：

```bash
export FIREBIRD_HOST=localhost
export FIREBIRD_PORT=3050
export FIREBIRD_DATABASE=/data/myapp.fdb
export FIREBIRD_USERNAME=SYSDBA
export FIREBIRD_PASSWORD=masterkey
export FIREBIRD_CHARSET=UTF8
```

然后从环境加载：

```python
config = FirebirdConnectionConfig.from_env()
```

## 连接管理

### 单连接

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

### 连接池

对于生产使用，启用连接池：

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

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

# 连接自动管理
```

### FastAPI 集成

```python
from fastapi import FastAPI
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

@app.on_event("shutdown")
async def shutdown():
    await backend.disconnect()
```

## 字符集/编码

### 默认编码

Firebird 后端默认使用 UTF-8 编码。您可以更改此设置：

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="ISO8859_1"  # 使用 Latin-1 编码
)
```

### 常见字符集

| 字符集 | 描述 |
|--------|------|
| `UTF8` | Unicode UTF-8（推荐） |
| `ISO8859_1` | Latin-1 |
| `WIN1252` | Windows Latin-1 |
| `ASCII` | ASCII |

💡 *AI 提示:* "国际应用程序应使用什么字符集？"