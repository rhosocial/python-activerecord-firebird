# 在 Firebird 后端上运行迁移

> **范围说明。** 本文假定读者已熟悉[核心库的迁移系统](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/migration/README.md)：
> 版本、方向、`@migration`、`run_migration_group`、`MigrationRecordStore`、
> `named-migration` 以及两套编写 API。本文**不**重复这些内容。以下只涉及通过**本**
> 后端运行迁移时特有的问题：如何配置 `firebird-driver`、Firebird 的事务性 DDL 对迁移
> 运行意味着什么、SQL 方言与服务器版本门控，以及两种编写风格的接线方式。凡是属于系统
> 本身而非 Firebird 的细节，一律留给核心章节说明。

> ⚠️ **仅支持同步。** `firebird-driver` 没有异步 API。`AsyncFirebirdBackend` 只是为保持
> API 形状一致而保留的线程池包装，本后端的 CLI 会**拒绝** `--async`（退出码 1）。请勿在
> 此处使用 `run_migration_group_async()` 或 `AsyncNamedMigration`；本页所有片段都是同步的。
> 参见[异步状态](../../en_US/introduction/supported_versions.md#async-status)。

## 1. 为本后端配置迁移

迁移使用的连接对象与本后端的其它功能相同。构造一个 `FirebirdConnectionConfig`，将其传给
`FirebirdBackend`，连接，并让方言适配服务器：

```python
from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig.from_env()  # FIREBIRD_* environment variables
backend = FirebirdBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()  # teach the dialect the server version before rendering gated DDL
```

`FirebirdConnectionConfig.from_env()` 读取 `FIREBIRD_HOST`、`FIREBIRD_PORT`、
`FIREBIRD_DATABASE`、`FIREBIRD_USERNAME`/`FIREBIRD_USER`、`FIREBIRD_PASSWORD`、
`FIREBIRD_CHARSET`、`FIREBIRD_ROLE` 以及连接池 / SSL 设置。显式构造配置同样可行：

```python
config = FirebirdConnectionConfig(
    database="localhost/3050:/var/lib/firebird/data/test.fdb",
    username="SYSDBA",
    password="masterkey",
    charset="UTF8",
)
```

`introspect_and_adapt()` 是最容易被遗漏的一步。本后端的方言根据适配后的服务器版本回答
能力查询；未适配的方言会拒绝受门控的特性，而不是猜测一个版本下限。由于 DDL 渲染会查询
同一套门控，请在迁移运行前调用它 —— `named-migration` CLI 会自动为你完成。连接参数与
环境变量见 [CLI 用法](../../en_US/cli/README.md) 与[连接配置](../../en_US/installation/configuration.md)。

迁移运行时请将 `FirebirdConnectionConfig.autocommit` 保持为默认值（`False`）；下文所述的
事务性行为依赖于语句留在事务之内。

## 2. 事务性 DDL 与版本记录

Firebird **确实**支持事务性 DDL。`FirebirdDialect.supports_transactional_ddl()` 返回
`True`：`CREATE`、`ALTER` 和 `DROP` 都参与事务，因此一组 schema 语句可以一起提交，也可以
作为一个整体回滚。如果你直接执行 DDL，请用后端的上下文管理器包裹：

```python
with backend.transaction():
    backend.execute(statement.to_sql()[0], fetch=False)
```

`run_migration_group` 使用自己的 `TransactionMode.AUTO` 默认值管理事务；该选项由核心章节
解释，此处不重复。对本后端而言，实际意义只是：失败的 DDL 语句不会留下半应用的 schema ——
事务可以回滚。

**版本记录位于数据库之外。** 内置的 `JSONFileMigrationRecordStore` 写入一个 JSON 文件，
该写入不属于 Firebird 事务。因此 DDL 回滚并不会回滚记录文件 —— 核心库只在运行成功后写入
记录，正是这一点让两者保持一致。请使用绝对且持久的路径（或自定义存储），并让 UP 与 DOWN
指向同一个文件。记录语义本身由核心章节说明。

## 3. SQL 方言、服务器版本与标识符折叠

有三个 Firebird 特有的细节会改变迁移 DDL 的行为：

- **数据库 SQL 方言（1 与 3）。** 每个 Firebird 数据库都带有自己的 SQL 方言。方言 3 是
  现代默认值，也是本后端的方言、类型渲染器与能力门控所针对的方言。遗留的方言 1 数据库在
  迁移相关的方面有差异 —— 例如 `NUMERIC`/`DECIMAL` 的处理方式，缺少方言 3 的原生
  `BOOLEAN` 与 identity 列等特性，以及带分隔符标识符的规则不同。对方言 3 渲染顺畅的迁移，
  可能被方言 1 数据库拒绝。如果必须处理遗留的方言 1 数据库，请先在副本上验证并规划向方言
  3 的转换；不要假定生成的 DDL 可以原样迁移。
- **标识符折叠。** 未加引号的名称会折叠为大写并由本方言加上引号。请对某张表在创建、删除
  与记录版本中使用一致的名称拼写；在自省或清理时混用 `widgets` 与 `WIDGETS` 是常见的迁移
  错误。参见[字段类型与方言](../../en_US/modeling/field_types.md#nullability-and-identifier-folding)。
- **版本门控特性。** 优先使用表达式对象（例如将模型的 `create_table_statement()` 传给
  `ctx.apply()`），而不是手写 SQL 文本：这样方言才能拒绝所连接服务器不支持的特性，而不是
  发出会被拒绝的 SQL。有代表性的门控如下：

| 特性 | 最低服务器版本 |
|------|----------------|
| `DATEDIFF`、事务性 DDL | 2.5 / 所有受支持版本 |
| CTE、窗口函数、`RETURNING`、`BOOLEAN`、identity 列、sequences、`OFFSET/FETCH` | 3.0 |
| `DECFLOAT`、`INT128`、带时区的时间类型、`SKIP LOCKED`、publications | 4.0 |

权威列表见[支持的版本](../../en_US/introduction/supported_versions.md)与
[能力门控与快速失败](../../en_US/introduction/capability_gates.md)。

## 4. 函数式迁移（同步）

这是推荐的方式。迁移函数通过 `ctx.apply()` 应用模型 DDL，`run_migration_group` 再通过本
后端的方言渲染它：

```python
from rhosocial.activerecord.backend.migration import (
    migration,
    MigrationDirection,
    run_migration_group,
)
from rhosocial.activerecord.backend.migration.record import JSONFileMigrationRecordStore


@migration("v001_create_widgets", description="create the widgets table")
def create_widgets(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(Widget.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(Widget.drop_table_statement(if_exists=True, backend=ctx.backend))


store = JSONFileMigrationRecordStore("/var/lib/firebird/migration_records.json")
fqn = "myapp.migrations:create_widgets"
preview = run_migration_group(backend, [fqn], dry_run=True)  # renders only; writes nothing
result = run_migration_group(backend, [fqn], record_store=store)
```

不要改用组运行器的异步对应版本：在本后端上，它只是把同样的驱动调用包进 executor。完整的
可运行流程（dry-run → UP → DOWN）见
[`docs/examples/migration/01_function_migration.py`](../../examples/migration/01_function_migration.py)。

## 5. 类式 `NamedMigration` 与 `named-migration` CLI（同步）

旧式类 API 仍受支持，用于维护既有迁移。类声明版本并实现 `up()`/`down()`；使用
`ctx.apply()` 可让 DDL 留在 Firebird 方言之内：

```python
from rhosocial.activerecord.backend.migration import (
    NamedMigration,
    MigrationContext,
    MigrationDirection,
    MigrationRunner,
    JSONFileMigrationRecordStore,
)


class V001CreateWidgets(NamedMigration):
    version = "v001_create_widgets"

    def up(self, ctx: MigrationContext) -> None:
        ctx.apply(Widget.create_table_statement(backend=ctx.backend))

    def down(self, ctx: MigrationContext) -> None:
        ctx.apply(Widget.drop_table_statement(if_exists=True, backend=ctx.backend))


runner = MigrationRunner("myapp.migrations.V001CreateWidgets")
result = runner.run(backend, MigrationDirection.UP, record_store=JSONFileMigrationRecordStore("records.json"))
```

同一个类也可以由本后端的 CLI 驱动。该命令会构造 `FirebirdBackend`、连接、调用
`introspect_and_adapt()`，然后分派给共享的迁移辅助函数：

```bash
python -m rhosocial.activerecord.backend.impl.firebird named-migration \
    myapp.migrations.V001CreateWidgets \
    --database localhost/3050:/var/lib/firebird/data/test.fdb \
    --direction up --record-store ./records.json
```

`--direction down`、`--list`、`--describe`、`--all`、`--single-transaction` 以及 `FIREBIRD_*`
连接参数 / 环境变量均可用；运行 `--help` 查看完整选项。传入 `--async` 会以解释性错误退出
（退出码 1）—— 官方驱动不支持异步，CLI 不会伪装成支持。

> 类式 `--dry-run` 只捕获通过命名表达式发出的 SQL；`ctx.apply()` 语句不在该摘要中。若要在
> 本后端上获得忠实的预览，请使用函数式 `run_migration_group(dry_run=True)` 路径。这一分工
> 在核心章节的 dry-run 一节中有说明。

编程方式与 CLI 接线示例见
[`docs/examples/migration/02_named_migration.py`](../../examples/migration/02_named_migration.py)。

## 6. 快速检查清单

1. 设置 `FIREBIRD_*`（或构造 `FirebirdConnectionConfig`）并保持 `autocommit=False`。
2. 用 `FirebirdBackend` 连接，并在渲染 DDL 前调用 `introspect_and_adapt()`。
3. 坚持同步 —— 不要用 `--async`、异步运行器或异步迁移类。
4. 通过表达式对象 / 模型渲染 DDL，使版本与方言门控生效。
5. 对表名使用一致的（大写）拼写；确认目标数据库是方言 3。
6. 将 `JSONFileMigrationRecordStore` 放在稳定的绝对路径上，并由 UP 与 DOWN 共用。

## 7. 延伸阅读

- [核心迁移系统](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/migration/README.md) —— 系统本身：顺序、依赖、记录、dry run、CLI 与异常。
- [核心迁移示例](https://github.com/rhosocial/python-activerecord/tree/main/docs/examples/migration) —— 更多函数式场景。
- [可运行的 Firebird 迁移示例](../../examples/migration/README.md)
- [事务与保存点](../../en_US/transactions/README.md) —— Firebird 事务语义。
