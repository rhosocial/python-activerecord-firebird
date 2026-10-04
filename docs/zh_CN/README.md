# rhosocial-activerecord Firebird 后端文档

Firebird 后端是 [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord)
的 Firebird 后端实现。它使用 `firebird-driver` 驱动，并按所连接服务器的具体版本来判定
能力——Firebird 的特性是随版本逐步加入的，并非一次性具备，因此方言不会假装这些能力
始终存在。

## 目录 (Table of Contents)

- **[Schema 命名空间](firebird_specific_features/schema_namespace.md)**：为什么 Firebird 会拒绝
  限定名而不是丢掉命名空间，以及依然生效的表名规则

## 关键结论速览

| 问题 | 结论 |
|---|---|
| schema 支持 | 无——限定名会抛 `UnsupportedFeatureError` |
| `supports_schema()` | `False` |
| 未限定的表渲染为 | `"T"` |
| 未限定的列渲染为 | `"T"."ID"` |
| `CREATE SCHEMA` / `DROP SCHEMA` | 本后端未实现 |
| 标识符大小写 | 除非另行要求，否则折叠为大写 |
| 表名参数 | 仍然只收 `TableExpression`；裸字符串抛 `TypeError` |

## 相关文档

- **[Schema 命名空间（核心库指南）](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)**：
  所有后端共同遵循的、与方言无关的规则

---

> ⚠️ **依赖说明**：本后端依赖核心库 `rhosocial-activerecord`，请与核心库一并安装，
> 不要单独安装本后端。
