# 连接配置

## 基本配置

### 配置类

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/var/lib/firebird/3.0/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)
```

### 配置选项

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `host` | str | `"localhost"` | Firebird 服务器主机名 |
| `port` | int | `3050` | Firebird 服务器端口 |
| `database` | str | None | 数据库路径或连接字符串 |
| `username` | str | None | 数据库用户名 |
| `password` | str | None | 数据库密码 |
| `role` | str | None | SQL 角色名称 |
| `charset` | str | `"UTF8"` | 连接字符集 |
| `page_size` | int | None | 数据库页面大小 |
| `wire_compression` | bool | `False` | 启用线路压缩 |
| `use_unicode` | bool | `True` | 使用 Unicode 字符串 |
| `autocommit` | bool | `False` | 启用自动提交模式 |
| `timeout` | int | None | 连接超时（秒） |

## 连接字符串

### 主机:端口格式

```python
config = FirebirdConnectionConfig(
    host="localhost",
    port=3050,
    database="/data/myapp.fdb"
)
```

### 完整 DSN

```python
# 用于远程数据库
config = FirebirdConnectionConfig(
    database="localhost/3050:/data/myapp.fdb"
)
```

### 嵌入模式

```python
# 用于嵌入式 Firebird
config = FirebirdConnectionConfig(
    database="/data/myapp.fdb"
)
```

## 环境变量

### 从环境加载

```python
config = FirebirdConnectionConfig.from_env()
```

### 环境变量映射

| 环境变量 | 配置选项 |
|----------|----------|
| `FIREBIRD_HOST` | `host` |
| `FIREBIRD_PORT` | `port` |
| `FIREBIRD_DATABASE` | `database` |
| `FIREBIRD_USERNAME` | `username` |
| `FIREBIRD_PASSWORD` | `password` |
| `FIREBIRD_ROLE` | `role` |
| `FIREBIRD_CHARSET` | `charset` |
| `FIREBIRD_PAGE_SIZE` | `page_size` |
| `FIREBIRD_POOL_SIZE` | `pool_size` |
| `FIREBIRD_POOL_TIMEOUT` | `pool_timeout` |
| `FIREBIRD_AUTOCOMMIT` | `autocommit` |
| `FIREBIRD_WIRE_COMPRESSION` | `wire_compression` |
| `FIREBIRD_TIMEOUT` | `timeout` |

## 高级配置

### 连接池

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)
```

### SSL/TLS

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    ssl=True,
    ssl_ca="/path/to/ca.pem",
    ssl_cert="/path/to/client-cert.pem",
    ssl_key="/path/to/client-key.pem"
)
```

### 时区

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timezone="America/New_York"
)
```

## 配置验证

### 测试配置

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)

# 验证配置
print(config.to_dict())
```

### 从文件加载

```python
import json

with open("config.json") as f:
    config_data = json.load(f)

config = FirebirdConnectionConfig(**config_data)
```

💡 *AI 提示:* "如何为生产环境配置 Firebird 连接池？"