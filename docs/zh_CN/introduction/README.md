# 介绍

## Firebird 后端概述

`rhosocial-activerecord-firebird` 是 rhosocial-activerecord 核心库的 Firebird 数据库后端实现。它提供完整的 ActiveRecord 模式支持，专门针对 Firebird 数据库功能进行了优化。

💡 *AI 提示:* "Firebird 与其他数据库有何不同？它的主要优势是什么？"

## 同步和异步

Firebird 后端提供功能等效的同步和异步 API。文档将全程使用同步示例，但异步 API 使用方法完全相同——只需将方法调用替换为相应的异步等效项。

例如：

```python
# 同步使用
backend = FirebirdBackend(...)
backend.connect()
users = backend.find('User')

# 异步使用
backend = AsyncFirebirdBackend(...)
await backend.connect()
users = await backend.find('User')
```

## 为什么需要命名功能？

命名功能允许您**将复杂配置编码为单个名称**，避免冗长的命令行参数，并支持无法通过 CLI 标志表达的参数组合。

**命名连接** — 封装所有连接参数：

```bash
# 不使用命名连接：长参数列表
rhosocial-activerecord-firebird query \
    --host prod-db.example.com --port 3050 --database /data/myapp.fdb \
    --user SYSDBA --password secret \
    "SELECT * FROM users"

# 使用命名连接：一个名称包含一切
rhosocial-activerecord-firebird query \
    --named-connection myapp.connections.prod_readonly \
    "SELECT * FROM users"
```

**命名表达式** — 封装复杂查询逻辑：

```bash
# 不使用命名表达式：难以转义的复杂 SQL
rhosocial-activerecord-firebird query \
    "SELECT u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE o.created_at >= '2026-01-01' GROUP BY u.id HAVING COUNT(o.id) > 5 ORDER BY order_count DESC ROWS 20"

# 使用命名表达式：一个名称，类型安全的参数
rhosocial-activerecord-firebird named-expression \
    myapp.queries.high_value_customers \
    --param since=2026-01-01 --param min_orders=5
```

**命名过程** — 封装多步骤工作流：

```bash
# 不使用命名过程：多个顺序命令
rhosocial-activerecord-firebird query "BEGIN TRANSACTION; ..."
rhosocial-activerecord-firebird query "UPDATE inventory ..."
rhosocial-activerecord-firebird query "INSERT INTO orders ..."
rhosocial-activerecord-firebird query "COMMIT;"

# 使用命名过程：一个命令，事务管理
rhosocial-activerecord-firebird named-procedure \
    myapp.workflows.place_order \
    --param user_id=42 --param product_id=100 --param quantity=3
```

**命名迁移** — 封装带依赖关系的版本化模式更改：

```bash
rhosocial-activerecord-firebird named-migration up add_users_table
rhosocial-activerecord-firebird named-migration down add_users_table
```

| 功能 | 优势 |
|------|------|
| 命名连接 | 将连接配置存储在可版本化的 Python 代码中；跨脚本共享 |
| 命名表达式 | 封装复杂 SQL；类型安全参数；跨工具重用 |
| 命名过程 | 带事务管理的多查询工作流；并行执行 |
| 命名迁移 | 带依赖跟踪的版本化模式更改；向上/向下支持 |

## 快速链接

- **[与核心库的关系](./relationship.md)**: 了解 Firebird 后端如何与核心库协作
- **[支持的版本](./supported_versions.md)**: 查看支持的 Firebird、Python 和依赖版本

💡 *AI 提示:* "Firebird 4.0 相比 Firebird 3.0 有哪些重要的新功能？"