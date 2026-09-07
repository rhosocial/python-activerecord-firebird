# DDL 特征 Spec

Firebird 从 `SQLDialectBase` 继承核心 DDL 特征认领协议（`dialect.build_spec`）——
通用 Spec 无需任何 Firebird 特定代码。

## 认领机制

`Model.generate_create_table(dialect)` 时，生成器把每个声明的 Spec 交给
`dialect.build_spec(spec)`：

- **接受** → 方言构造并返回表达式层实例，进入 `CreateTableExpression`；
- **不接受** → 返回 `None`，该 Spec 被静默忽略。

## 通用 Spec

全部通用 Spec 由核心默认翻译认领：

| Spec | Firebird 翻译 |
|------|---------------|
| `CheckSpec` | `TableConstraint(CHECK)`，惰性谓词生成时求值 |
| `UniqueSpec` | `TableConstraint(UNIQUE)` |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | 单列→列级 PK / 复合→表级 PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)`，参数化 `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint`（含参照动作） |
| `IndexSpec` | `IndexDefinition` |
| `JsonColumnSpec` | 列类型补丁 → `JsonType` |

## 分区

Firebird 不支持表分区——全部分区能力位报告 `False`，不认领任何分区 Spec，
声明的 `__table_partition__` 被忽略（建普通表）。
