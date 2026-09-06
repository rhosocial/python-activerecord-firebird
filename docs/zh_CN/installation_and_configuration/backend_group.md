# BackendGroup 与 BackendManager（Firebird）

本文档介绍如何在 Firebird 后端使用 `BackendGroup` 和 `BackendManager`。详细 API 文档请参考[核心库文档](../../../rhosocial-activerecord/docs/zh_CN/connection/connection_management.md)。

## 后端组架构

`rhosocial-activerecord` 采用命名空间包（namespace package）布局：每个后端在独立仓库中维护，并安装到 `rhosocial.activerecord.backend.impl` 命名空间下。例如，Firebird 后端位于 `rhosocial.activerecord.backend.impl.firebird`。这种设计允许多个后端——SQLite、MySQL、PostgreSQL、Firebird 等——共存于同一环境中。

`BackendGroup` 将一组模型绑定到单个后端实例（一个连接目标），而 `BackendManager` 管理多个组，使不同的模块或租户可以使用各自的数据库。Firebird 后端通过 `FirebirdBackend` 和 `FirebirdConnectionConfig` 接入这一架构。

## 快速示例

```python
from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend, FirebirdConnectionConfig
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    name: str
    email: str


# 使用上下文管理器
with BackendGroup(
    name="main",
    models=[User],
    config=FirebirdConnectionConfig(
        host="localhost",
        port=3050,
        database="/var/lib/firebird/3.0/data/myapp.fdb",
        username="SYSDBA",
        password="masterkey",
    ),
    backend_class=FirebirdBackend,
) as group:
    user = User(name="John", email="john@example.com")
    user.save()

# 使用 BackendManager 管理多个数据库
from rhosocial.activerecord.connection import BackendManager

manager = BackendManager()
manager.create_group(
    name="main",
    models=[User],
    config=FirebirdConnectionConfig(host="localhost", database="/data/main.fdb"),
    backend_class=FirebirdBackend,
)
manager.create_group(
    name="stats",
    config=FirebirdConnectionConfig(host="localhost", database="/data/stats.fdb"),
    backend_class=FirebirdBackend,
)

main_backend = manager.get_group("main").get_backend()
stats_backend = manager.get_group("stats").get_backend()
```

## 使用表达式查询

请使用表达式类构建查询，而不是原始 SQL 字符串。使用 `with_()` 预先加载关联记录：

```python
# 预先加载活跃用户关联的 posts
users = User.query().with_('posts').where(User.c.status == 'active').all()
```

表达式通过 `to_sql()` 生成 `(sql, params)` 二元组：

```python
from rhosocial.activerecord.backend.expression import Column, Literal

dialect = backend.dialect
expr = Column(dialect, "status") == Literal(dialect, "active")
sql, params = expr.to_sql()
# sql    -> 'status = ?'
# params -> ('active',)
```

## Firebird 特有功能

### 连接池配置

Firebird 后端使用 `DBUtils` 实现连接池。请通过 `pooling` 额外选项安装，并在 `FirebirdConnectionConfig` 上配置连接池字段：

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,      # 启用连接池，包含 5 个连接
    pool_timeout=30,  # 等待空闲连接的秒数
)
```

### 字符集与线路压缩

Firebird 连接默认使用 UTF-8。可按需在配置中设置 `charset`、`use_unicode` 和 `wire_compression`：

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8",
    use_unicode=True,
    wire_compression=True,
)
```

### 服务器端服务

Firebird 数据库通常由 `fbguard` 服务托管，该服务监控 `fbserver` 并在其崩溃后自动重启。`fbguard` 在服务器端运行；从后端角度看，连接就是普通的 `localhost:3050` TCP 连接，因此 `FirebirdConnectionConfig` 无需特殊配置。