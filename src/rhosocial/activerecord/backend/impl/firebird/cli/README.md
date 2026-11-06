# `introspect` — Firebird metadata, from the command line

The `introspect` subcommand asks a live Firebird database what it holds, and
prints the answer. Every question runs through the backend's introspector, so
what the CLI reports is what the library sees — the same objects, the same
types, the same parsing — rather than a second implementation that can drift
from it. Thirty types are advertised, derived from `_TYPE_CAPABILITIES` in the
source rather than written out a second time, so a family cannot be answerable
and unaskable at once.

```bash
python -m rhosocial.activerecord.backend.impl.firebird introspect <TYPE> [NAME] [OPTIONS]
```

## What it can ask about

Thirty types, in the order `--help` prints them. The twenty-two catalogue
families each answer `True`; the eight offered beyond the catalogue answer
`True` for the three that read the rows and `False` for the five the engine
declines, so a run of those is refused (exit 2) rather than reached and answered
with an empty row.

| Type | Reads | Notes |
| :--- | :--- | :--- |
| `tables` | `rdb$relations` | Base tables. `--include-system` adds the engine's own. Answering for the whole database, it reads no NAME — and unlike `unused-indexes` below it is not gated, so a name given here is passed to the parser's optional positional and then ignored by the branch. |
| `views` | `rdb$relations` | Views, with their definitions. `NAME` narrows it to one view. |
| `columns` | `rdb$relation_fields`, `rdb$fields` | One table's columns: name, type, nullability, default, and the domain each is built on. |
| `indexes` | `rdb$indices`, `rdb$index_segments` | One table's indexes, including the primary key. |
| `foreign-keys` | `rdb$ref_constraints`, `rdb$relation_constraints` | One table's constraints and the columns each side names. |
| `triggers` | `rdb$triggers` | Triggers, optionally narrowed to one table. |
| `database` | `rdb$database`, `mon$` | Server version and the database's own facts. |
| `generators` | `rdb$generators` | Firebird's sequences. The value is read with `GEN_ID(<name>, 0)`, which is a read and not an advance. |
| `domains` | `rdb$fields` | Domains with base type, length, charset, nullability, `DEFAULT` source and check source. |
| `exceptions` | `rdb$exceptions` | Exception messages with their number and owner. |
| `procedures` | `rdb$procedures` | Stored procedures with their source, input/output arity, type and security class. |
| `procedure-parameters` | `rdb$procedure_parameters` | One procedure's parameters, in position order, typed through their domain. |
| `functions` | `rdb$functions` | User-defined functions (Firebird 3+), including the engine, module and entrypoint of an external one. |
| `function-arguments` | `rdb$function_arguments` | One function's arguments, in position order. |
| `constraints` | `rdb$relation_constraints`, `rdb$check_constraints` | Table constraints of every kind, with the trigger that enforces a `CHECK`. |
| `roles` | `rdb$roles` | Roles, with the system flag and the system privileges granted to each. |
| `privileges` | `rdb$user_privileges` | Grants per object and grantee. `--object` and `--grantee` narrow it. |
| `charsets` | `rdb$character_sets` | Character sets with their form of use, character width and default collation. |
| `collations` | `rdb$collations` | Collations with the charset they belong to and their base collation. |
| `rdb-dependencies` | `rdb$dependencies` | What depends on what, by name and type. |
| `view-relations` | `rdb$view_relations` | The relations a view selects from, with each one's context name. |
| `publications` | `rdb$publications` | Logical-replication publications. Version-gated: `rdb$publications` does not exist before Firebird 4, so an older server is refused (exit 2) rather than answered "none". |
| `unused-indexes` | refused here | Offered and gated: `supports_unused_indexes_detection` answers False here, so the run is refused rather than answered empty. |
| `table-stats` | refused here | Offered and gated on `supports_table_stats`, which answers False here. |
| `runtime` | refused here | Offered and gated on `supports_runtime_stats`, which answers False here. |
| `index-stats` | refused here | Offered and gated on `supports_index_stats`, which answers False here. |
| `ddl` | refused here | Offered and gated on `supports_ddl_extraction`: Firebird records a source body rather than a rebuildable `CREATE`, so an assembled fragment would read as authoritative. |
| `column-profiles` | the rows themselves | Answers True here: the profile is one aggregate over the rows. A `BLOB` reports its null count and the row count and nothing else — Firebird refuses `MIN`, `MAX` and `COUNT(DISTINCT ...)` on a type it cannot compare, so those figures are absent rather than zero. |
| `value-samples` | the rows themselves | Answers True here, read from the rows; `--column` names the column. |
| `join-coverage` | the rows themselves | Answers True here: how much two columns' value domains overlap. `--column`, `--right-table` and `--right-column` are required. |

### What `NAME` means

| Meaning | Types |
| :--- | :--- |
| A **table**, required | `columns`, `indexes`, `foreign-keys` |
| The **object itself**, required | `procedure-parameters`, `function-arguments` |
| A **table**, optional | `triggers` |
| The **object itself**, optional — given, it answers for that one object and exits 1 if there is no such object | `views`, `generators`, `domains`, `exceptions`, `procedures`, `functions` |
| A **filter** | `privileges` (`--object`, `--grantee`), `constraints` (`--constraint-type`) |
| The whole database, and a stray NAME is refused (exit 2) | `unused-indexes`, `table-stats`, `runtime`, `index-stats` |
| The whole database, and the parser accepts a NAME that the branch does not read | `tables`, `database`, `roles`, `charsets`, `rdb-dependencies`, `view-relations`, `publications` |
| A **table**, required, though its switch answers False here | `ddl`, `column-profiles`, `value-samples` |
| The **left table**, required — the column is `--column` and the right-hand side is `--right-table` / `--right-column` | `join-coverage` |

`collations` takes an optional charset as its `NAME`, and `rdb-dependencies` and
`view-relations` accept one to narrow the answer; they are not in the refused
row for that reason. The `NAME` for `ddl` and the two row families is the table,
and the column a question is about is a flag rather than a second positional,
because `value-samples orders.email` would read as a dotted object name.

Only the four operational families actually call `_refuse_name`, so they are the
only ones whose exit 2 says "this type takes no name". The other whole-database
types are not gated either way: a NAME supplied there is accepted by argparse
and ignored by the branch, which is a real difference from a refusal and is why
the two rows above are kept apart rather than merged. The gate that refuses
`ddl` and the row families is the capability question, not the `NAME` rule.

## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
| `--host`, `--port`, `--database` / `-d` | env or defaults | Connection. `FIREBIRD_*` env vars are honoured, and arguments override them. |
| `--user` / `-u`, `--password` / `-p` | env | Credentials. |
| `--charset` | _None_ | Connection charset. |
| `--role` | _None_ | SQL role to assume. |
| `--ssl` | off | Use SSL for the connection. |
| `--async` | off | Drive the asynchronous backend. |
| `--named-connection` | _None_ | A connection saved by the `named-connection` subcommand. |
| `--conn-param` | _None_ | Extra `key=value` connection parameters; repeatable. |
| `--rich-ascii` | off | ASCII characters for table borders. |
| `--column` | _None_ | The column a `value-samples` or `join-coverage` question is about. |
| `--right-table`, `--right-column` | _None_ | The right-hand side of a `join-coverage` question. |

## Notes

*   **Read-only.** `introspect` never writes. It does not create, drop, or
    alter anything, so it is safe to run against a database whose schema
    matters.
*   **There is no namespace flag, and that is deliberate.** Firebird has a
    single unnamed namespace: every object lives in the one database the
    connection opens, and nothing qualifies a name above it. An earlier version
    accepted `--schema`, which named a level this engine does not have; it is
    gone rather than aliased.
*   **Catalogue names are upper case and space-padded.** Firebird stores
    `CHAR` columns padded, so the introspector strips them; a name that is
    only padding is not an object.
*   **Names fold unless quoted.** `my_gen` names `MY_GEN`. An exact match is
    tried first, so two names differing only by case stay distinguishable, and
    the folded match is second.
*   **`generators` costs one extra question per generator**, because a
    generator's value lives in the engine and not in the catalogue. The result
    is cached, so it is paid once per cache generation rather than per call.
*   **One question per invocation.** A CLI process is one connection that
    opens, answers, and closes — there is no cache carried between runs.
*   **A family this server cannot answer says so, with its own exit code.**
    `publications` arrived in Firebird 4, so it is gated on the dialect's
    version rather than on the release this backend knows. Refusal exits 2 —
    "here is no such question" — while 1 means the request failed while
    running. The gate is fed by `_TYPE_CAPABILITIES`, one switch per family.
*   **The families beyond the catalogue are offered, and offer is the point.**
    The four operational families and `ddl` answer `False` on this dialect —
    Firebird's catalogue describes objects rather than a statistics collector,
    and it records a source body rather than a rebuildable `CREATE` — so those
    five are refused with exit 2 rather than answered with an empty row, which
    would read as an answer of zero. The three row families answer True: they
    read the table itself, one aggregate for a profile and one grouped read for
    a value listing, both exact and both paid for in time.
*   **`get_supported_introspection_scopes()` names eight of the thirty
    families**, because core's `IntrospectionScope` has no member for domains,
    exceptions, routines, roles, privileges, charsets, collations,
    dependencies, view relations or publications. The list is what core can
    *express*; `_TYPE_CAPABILITIES` is what this backend can *answer*, which is
    the longer list. Adding members to that enum is a core decision (it keys
    the introspection cache), not one this backend takes on its own.

## Examples

```bash
# The families Firebird has and most engines do not
python -m rhosocial.activerecord.backend.impl.firebird introspect generators
python -m rhosocial.activerecord.backend.impl.firebird introspect domains -o json
python -m rhosocial.activerecord.backend.impl.firebird introspect exceptions
python -m rhosocial.activerecord.backend.impl.firebird introspect procedures
python -m rhosocial.activerecord.backend.impl.firebird introspect charsets

# One object of a family that answers for one
python -m rhosocial.activerecord.backend.impl.firebird introspect views orders_v
python -m rhosocial.activerecord.backend.impl.firebird introspect procedures transfer

# A table's shape, one question at a time
python -m rhosocial.activerecord.backend.impl.firebird introspect columns orders
python -m rhosocial.activerecord.backend.impl.firebird introspect foreign-keys orders

# A specific database file
python -m rhosocial.activerecord.backend.impl.firebird introspect tables -d /var/lib/firebird/data/shop.fdb

# What the rows hold, not what the columns declare -- read from the rows, so exact and paid for
python -m rhosocial.activerecord.backend.impl.firebird introspect column-profiles orders
python -m rhosocial.activerecord.backend.impl.firebird introspect value-samples orders --column status
python -m rhosocial.activerecord.backend.impl.firebird introspect join-coverage orders --column customer_id --right-table customers --right-column id

# Questions this dialect declines -- exit 2, "not supported by this server", not an empty list
python -m rhosocial.activerecord.backend.impl.firebird introspect unused-indexes
python -m rhosocial.activerecord.backend.impl.firebird introspect ddl orders
```
