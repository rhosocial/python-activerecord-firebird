# `introspect` — Firebird metadata, from the command line

The `introspect` subcommand asks a live Firebird database what it holds, and
prints the answer. Every question runs through the backend's introspector, so
what the CLI reports is what the library sees — the same objects, the same
types, the same parsing — rather than a second implementation that can drift
from it.

```bash
python -m rhosocial.activerecord.backend.impl.firebird introspect <TYPE> [NAME] [OPTIONS]
```

## What it can ask about

| Type | Reads | Notes |
| :--- | :--- | :--- |
| `tables` | `rdb$relations` | Base tables. `--include-system` adds the engine's own. `NAME` is refused: it answers for the whole database. |
| `views` | `rdb$relations` | Views, with their definitions. `NAME` narrows it to one view. |
| `columns` | `rdb$relation_fields`, `rdb$fields` | One table's columns: name, type, nullability, default, and the domain each is built on. |
| `indexes` | `rdb$indices`, `rdb$index_segments` | One table's indexes, including the primary key. |
| `foreign-keys` | `rdb$ref_constraints`, `rdb$relation_constraints` | One table's constraints and the columns each side names. |
| `triggers` | `rdb$triggers` | Triggers, optionally narrowed to one table. |
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
| `dependencies` | `rdb$dependencies` | What depends on what, by name and type. |
| `view-relations` | `rdb$view_relations` | The relations a view selects from, with each one's context name. |
| `publications` | `rdb$publications` | Logical-replication publications (Firebird 4+). |
| `database` | `rdb$database`, `mon$` | Server version and the database's own facts. |

### What `NAME` means

| Meaning | Types |
| :--- | :--- |
| A **table**, required | `columns`, `indexes`, `foreign-keys` |
| The **object itself**, required | `procedure-parameters`, `function-arguments` |
| A **table**, optional | `triggers` |
| The **object itself**, optional — given, it answers for that one object and exits 1 if there is no such object | `views`, `generators`, `domains`, `exceptions`, `procedures`, `functions` |
| A **filter** | `privileges` (`--object`, `--grantee`), `constraints` (`--constraint-type`) |
| **Refused** — the type answers for the whole database | `tables`, `database`, `roles`, `charsets`, `collations`, `dependencies`, `view-relations`, `publications` |

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
*   **`get_supported_introspection_scopes()` names eight of the twenty-two
    families**, because core's `IntrospectionScope` has no member for domains,
    exceptions, routines, roles, privileges, charsets, collations,
    dependencies, view relations or publications. The list is what core can
    *express*; `_TYPE_CAPABILITIES` is what this backend can *answer*. Adding
    members to that enum is a core decision (it keys the introspection cache),
    not one this backend takes on its own.

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
```
