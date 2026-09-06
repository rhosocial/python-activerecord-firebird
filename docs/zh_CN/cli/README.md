# 命令行接口

## 概述

Firebird 后端包含用于数据库操作的命令行接口 (CLI)。CLI 提供用于查询、内省和管理 Firebird 数据库的命令，无需编写 Python 代码。

CLI 命令分为两类：

1. **后端特定命令** — Firebird 独特操作（查询、内省、信息、状态）
2. **核心继承命令** — 所有后端共享（named-expression、named-procedure、named-procedure-graph、named-migration、named-connection）

## 调用

安装包时，CLI 安装为 `rhosocial-activerecord-firebird`：

```bash
pip install rhosocial-activerecord-firebird
```

然后直接调用命令：

```bash
rhosocial-activerecord-firebird <command> [options]
```

此命令在 `pyproject.toml` 中注册，等效于 `python -m rhosocial.activerecord.backend.impl.firebird`。

## 输出格式

CLI 通过 `-o` / `--output` 选项支持多种输出格式：

| 格式 | 描述 | 需要 Rich |
|------|------|-----------|
| `table` | 带边框的人类可读表格（默认） | 是 |
| `json` | JSON 对象数组 | 否 |
| `csv` | 逗号分隔值 | 否 |
| `tsv` | 制表符分隔值 | 否 |

安装 Rich 时，`table` 格式提供带彩色边框的美化输出。未安装 Rich 时，CLI 自动回退到 `json` 格式。

### Rich 集成

CLI 与 [Rich](https://github.com/Textualize/rich) 库集成，提供增强的终端输出：

- **彩色边框**: 用于表格边框的 Unicode 绘图字符
- **ASCII 回退**: 使用 `--rich-ascii` 强制 ASCII 边框 (`+`, `-`, `|`)
- **自动检测**: 如果未安装 Rich，自动回退到 JSON 输出

```bash
# 默认表格输出（Unicode 边框）
rhosocial-activerecord-firebird query ... "SELECT * FROM users;"

# ASCII 边框（用于不支持 Unicode 的终端）
rhosocial-activerecord-firebird query ... --rich-ascii "SELECT * FROM users;"

# 强制 JSON 输出
rhosocial-activerecord-firebird query ... -o json "SELECT * FROM users;"
```

### 输出示例

**表格格式（默认）：**
```
┌─────┬─────────┬───────┐
│ id  │ name    │ email │
├─────┼─────────┼───────┤
│ 1   │ Alice   │ a@x   │
│ 2   │ Bob     │ b@x   │
└─────┴─────────┴───────┘
```

**JSON 格式：**
```json
[
  {"id": 1, "name": "Alice", "email": "a@x"},
  {"id": 2, "name": "Bob", "email": "b@x"}
]
```

**CSV 格式：**
```csv
id,name,email
1,Alice,a@x
2,Bob,b@x
```

**TSV 格式：**
```tsv
id	name	email
1	Alice	a@x
2	Bob	b@x
```

## 后端特定命令

这些命令由 Firebird 后端实现，直接与 Firebird 交互：

| 命令 | 描述 | 需要连接 |
|------|------|----------|
| `info` | 显示环境和协议信息 | 否 |
| `query` | 执行 SQL 查询 | 是 |
| `introspect` | 数据库内省（表、列、索引等） | 是 |
| `status` | 显示服务器状态和配置 | 是 |

### info

无需数据库连接即可显示环境信息：

```bash
rhosocial-activerecord-firebird info
```

### query

直接执行 SQL 查询：

```bash
rhosocial-activerecord-firebird query \
    --host localhost --port 3050 --database /data/myapp.fdb \
    --user SYSDBA --password masterkey \
    "SELECT * FROM users LIMIT 10"
```

### introspect

检查数据库元数据：

```bash
# 列出所有表
rhosocial-activerecord-firebird introspect tables \
    --host localhost --port 3050 --database /data/myapp.fdb

# 描述特定表
rhosocial-activerecord-firebird introspect table users \
    --host localhost --port 3050 --database /data/myapp.fdb

# 列出列
rhosocial-activerecord-firebird introspect columns users \
    --host localhost --port 3050 --database /data/myapp.fdb
```

#### 内省类型

Firebird 支持这些内省类型：

| 类型 | 描述 |
|------|------|
| `tables` | 列出所有表 |
| `views` | 列出所有视图 |
| `table` | 描述特定表 |
| `columns` | 列出表的列 |
| `indexes` | 列出表的索引 |
| `foreign-keys` | 列出表的外键 |
| `triggers` | 列出触发器 |
| `database` | 数据库信息 |
| `generators` | 列出生成器（序列） |
| `procedures` | 列出存储过程 |

### status

显示服务器状态：

```bash
rhosocial-activerecord-firebird status \
    --host localhost --port 3050 --database /data/myapp.fdb
```

## 核心继承命令

这些命令**从核心 `python-activerecord` 库继承**，在所有后端中完全相同地工作。后端 CLI 只是委托给共享的核心基础设施：

```
后端 CLI 适配器（薄包装器）
    └── 核心 CLI 助手（共享逻辑）
        ├── Resolver — 通过完全限定名加载 Python 可调用对象
        ├── Runner — 使用事务管理执行
        └── CLI 适配器 — 参数解析和输出
```

### 为什么需要命名功能？

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

### 命令参考

| 命令 | 源模块 | 描述 |
|------|--------|------|
| `named-expression` | `backend.named_expression` | 执行在 Python 中定义的类型安全参数化 SQL |
| `named-procedure` | `backend.named_expression.procedure` | 执行带事务支持的多查询编排 |
| `named-procedure-graph` | `backend.named_expression.procedure` | 执行过程图（DAG 工作流） |
| `named-migration` | `backend.migration` | 执行带依赖跟踪的版本化模式更改 |
| `named-connection` | `backend.named_connection` | 管理和测试命名连接配置 |

### named-expression

执行命名表达式（在 Python 模块中定义的参数化 SQL）：

```bash
rhosocial-activerecord-firebird named-expression <expression_name> \
    --host localhost --port 3050 --database /data/myapp.fdb
```

### named-procedure

执行命名过程：

```bash
rhosocial-activerecord-firebird named-procedure <procedure_name> \
    --host localhost --port 3050 --database /data/myapp.fdb
```

### named-procedure-graph

执行过程图（DAG 工作流）：

```bash
rhosocial-activerecord-firebird named-procedure-graph <graph_name> \
    --host localhost --port 3050 --database /data/myapp.fdb
```

### named-migration

执行命名迁移：

```bash
# 向上运行迁移
rhosocial-activerecord-firebird named-migration up <migration_name> \
    --host localhost --port 3050 --database /data/myapp.fdb

# 向下运行迁移
rhosocial-activerecord-firebird named-migration down <migration_name> \
    --host localhost --port 3050 --database /data/myapp.fdb
```

### named-connection

管理和测试命名连接配置：

```bash
rhosocial-activerecord-firebird named-connection <connection_name> \
    --params key=value
```

## 连接参数

所有需要数据库连接的命令都接受这些通用参数：

| 参数 | 描述 |
|------|------|
| `--host` | 数据库服务器主机名 |
| `--port` | 数据库服务器端口 |
| `--database` | 数据库名称或路径 |
| `--user` | 认证用户名 |
| `--password` | 认证密码 |
| `--async` | 使用异步后端 |
| `--named-connection` | 使用命名连接配置 |
| `--conn-param` | 附加连接参数 |
| `--log-level` | 设置日志级别 (DEBUG, INFO, WARNING, ERROR) |

## 全局选项

| 选项 | 描述 |
|------|------|
| `-h`, `--help` | 显示帮助消息并退出 |
| `--log-level` | 设置日志级别 (DEBUG, INFO, WARNING, ERROR) |

## 架构

CLI 在所有后端中遵循一致的架构：

```
backend/impl/firebird/
├── __main__.py          # 入口点，构建解析器，分派到处理程序
└── cli/
    ├── __init__.py      # COMMAND_NAMES 列表，register_commands()
    ├── connection.py    # 连接参数解析和后端创建
    ├── output.py        # 输出格式提供程序 (Rich/JSON/CSV/TSV)
    │
    │   # 后端特定命令
    ├── info.py          # 'info' 命令处理程序
    ├── query.py         # 'query' 命令处理程序
    ├── introspect.py    # 'introspect' 命令处理程序
    ├── status.py        # 'status' 命令处理程序
    │
    │   # 核心继承命令（薄适配器）
    ├── named_expression.py      # 委托给核心 named_expression.cli
    ├── named_procedure.py       # 委托给核心 named_expression.procedure.cli
    ├── named_procedure_graph.py # 委托给核心 named_expression.procedure.cli
    ├── named_migration.py       # 委托给核心 migration.cli
    └── named_connection.py      # 委托给核心 named_connection.cli
```

## 另请参阅

- [安装指南](../installation_and_configuration/installation.md) — 设置说明
- [连接管理](../installation_and_configuration/pool.md) — 连接配置
- [核心命名功能](https://github.com/Rhosocial/python-activerecord/tree/main/docs/zh_CN) — 命名连接、表达式、过程、迁移文档

💡 *AI 提示:* "如何从命令行列出 Firebird 数据库中的所有表？"