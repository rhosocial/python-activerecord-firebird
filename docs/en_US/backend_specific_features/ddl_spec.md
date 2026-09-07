# DDL Feature Specs

Firebird inherits the core DDL feature-spec claiming protocol
(`dialect.build_spec`) from `SQLDialectBase` — no Firebird-specific code is
required for the generic Specs.

## How claiming works

At `Model.generate_create_table(dialect)` time the generator hands each
declared Spec to `dialect.build_spec(spec)`:

- **Accepted** → the dialect builds and returns an expression-layer instance,
  which lands in the `CreateTableExpression`;
- **Not accepted** → returns `None`, and the Spec is silently ignored.

## Generic Specs

All generic Specs are claimed and translated by the core default:

| Spec | Firebird translation |
|------|----------------------|
| `CheckSpec` | `TableConstraint(CHECK)`, lazy predicates evaluated at build time |
| `UniqueSpec` | `TableConstraint(UNIQUE)` |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | column-level PK (single) / table-level composite PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)` with a parameterized `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint` with referential actions |
| `IndexSpec` | `IndexDefinition` |
| `JsonColumnSpec` | column type patch → `JsonType` |

## Partitions

Firebird does not support table partitioning — all partition capability flags
report `False`, no partition Spec is claimed, and a declared
`__table_partition__` is ignored (a plain table is built).
