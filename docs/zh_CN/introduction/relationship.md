# 与核心库的关系

## 概述

`rhosocial-activerecord-firebird` 后端与 `rhosocial-activerecord` 核心库集成，在保持 ActiveRecord 模式接口的同时提供 Firebird 数据库支持。

## 架构

```
rhosocial-activerecord (核心)
├── ActiveRecord 基类
├── 查询构建器
├── 事务管理
└── 类型系统

rhosocial-activerecord-firebird (后端)
├── FirebirdBackend 实现
├── Firebird 特定类型
├── Firebird 方言
└── Firebird 适配器
```

## 集成点

### 模型注册

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    name: str
    email: str

# 使用 Firebird 后端配置
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey"
)
User.configure(config, FirebirdBackend)
```

### 查询执行

后端实现核心存储接口：

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.operators import BinaryExpression

# 核心查询构建器使用表达式
expr = BinaryExpression(dialect, "=", Column(dialect, "active"), Literal(dialect, True))
users = User.query().where(expr).all()
sql, params = expr.to_sql()
# sql: "active" = %s
# params: (True,)

# 后端针对 Firebird 执行
# 使用 Firebird 特定的 SQL 方言
```

### 事务管理

```python
# 核心事务 API
with User.transaction():
    user = User(name="Alice")
    user.save()
    
    order = Order(user_id=user.id, amount=100)
    order.save()
```

## 功能映射

| 核心功能 | Firebird 实现 |
|----------|---------------|
| 模型 | FirebirdBackend 处理存储 |
| 查询 | Firebird SQL 方言 |
| 事务 | FirebirdTransactionManager |
| 类型系统 | FirebirdTypeAdapter |
| DDL | FirebirdDialect 扩展 |

## 兼容性

- **核心版本**: 需要 `rhosocial-activerecord>=1.0.0`
- **Python**: 3.11+
- **API 表面**: 完整的同步/异步对等

💡 *AI 提示:* "Firebird 后端如何扩展核心 ActiveRecord 功能？"