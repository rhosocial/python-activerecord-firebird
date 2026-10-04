# Firebird Schema 命名空间

**本后端的 Firebird 不支持 schema。**任何试图限定名字的调用都会抛
`UnsupportedFeatureError`，而不是悄悄渲染成未限定的形式。

所以本页很短。但它值得被认真读完，因为这种拒绝是有意为之：另一种做法——丢掉命名空间、
返回一段指向另一个对象的 SQL——正是本后端在其余各处都刻意避免的失败模式。

与方言无关的共同规则请阅读
[核心库指南](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)。

## 限定名字时会发生什么

该方言在结构上满足 `SchemaSupport` 协议，所以限定这条路径是接通的，而它的能力探测会如实
汇报：

```python
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport

isinstance(dialect, SchemaSupport)   # True  —— 路径已接通
dialect.supports_schema()            # False —— 并且它没有可提供的命名空间
```

渲染路径正是看这个探测结果，所以限定名会被拒绝：

```python
from rhosocial.activerecord.backend.expression.core import TableExpression

TableExpression(dialect, "t").to_sql()[0]
# "T"

TableExpression(dialect, "t", schema_name="app").to_sql()[0]
# UnsupportedFeatureError
```

```
UnsupportedFeatureError: 'Firebird' dialect does not support a schema-qualified
reference. Suggestion: Firebird has no namespace to qualify into, so
schema_name='app' cannot be used. TableExpression would render it as a name this
backend rejects.
```

列的限定同样被拒绝：

```python
from rhosocial.activerecord.backend.expression.core import Column

Column(dialect, "id", table="t").to_sql()[0]
# "T"."ID"

Column(dialect, "id", table="t", schema_name="app").to_sql()[0]
# UnsupportedFeatureError
```

索引也一样，只要你限定了它所属的表：

```python
CreateIndexExpression(
    dialect, "idx_t_id",
    TableExpression(dialect, "t", schema_name="app"),   # 在这里被拒绝
    ["id"],
).to_sql()[0]
# UnsupportedFeatureError
```

未限定的索引则没有问题：

```python
CreateIndexExpression(dialect, "idx_t_id", TableExpression(dialect, "t"), ["id"]).to_sql()[0]
# CREATE INDEX "IDX_T_ID" ON "T" ("ID")
```

## 同样没有 schema DDL

```
dialect.supports_create_schema()   # False
dialect.supports_drop_schema()     # False
```

限定被拒绝、创建命名空间未实现——两件事同源，所以两者都拿不到。

## 表名的规则依然生效

没有 schema，并不意味着表名的写法可以放松。各语句仍然只接受 `TableExpression`，裸字符串
会被拒绝：

```python
CreateTableExpression(dialect, "t", columns)   # TypeError
DropTableExpression(dialect, "t")              # TypeError
TruncateExpression(dialect, "t")               # TypeError
AlterTableExpression(dialect, "t", actions)    # TypeError
InsertExpression(dialect, "t", source)         # TypeError
DeleteExpression(dialect, "t")                 # TypeError
```

```
TypeError: table must be a TableExpression, got str
```

这是 schema 契约中唯一一个所有后端都相同的部分，而它在这里成立的理由也很朴素：这条规则
关乎把一张表 unambiguous 地指出来，与命名空间无关。

## 大小写折叠

未加引号的标识符会被折叠为大写。这是服务器的规则，不是库的规则：

```python
TableExpression(dialect, "t").to_sql()[0]   # "T"，而不是 "t"
Column(dialect, "id", table="t").to_sql()[0] # "T"."ID"
```

若需要保留原样写出的大小写，请传入 `name_need_quote=False` 等参数。

## 速查表

| 写法 | 结果 |
|---|---|
| `TableExpression(d, "t")` | `"T"` |
| `Column(d, "id", table="t")` | `"T"."ID"` |
| `CreateTableExpression(d, "t", cols)` | `TypeError` |
| `TableExpression(d, "t", schema_name="app")` | `UnsupportedFeatureError` |
| `Column(d, "id", table="t", schema_name="app")` | `UnsupportedFeatureError` |
