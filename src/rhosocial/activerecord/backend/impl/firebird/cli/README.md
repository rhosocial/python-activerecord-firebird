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
| `tables` | `rdb$relations`, `rdb$relation_fields` | Base tables. `--include-system` adds the engine's own. |
| `views` | `rdb$relations` | Views, with their definitions. |
| `table` | several | One table by name, with its columns, indexes and foreign keys filled in. |
| `columns` | `rdb$relation_fields`, `rdb$fields` | One table's columns: name, type, nullability, default, and the domain each is built on. |
| `indexes` | `rdb$indices`, `rdb$index_segments` | One table's indexes, including the primary key. |
| `foreign-keys` | `rdb$ref_constraints`, `rdb$relation_constraints` | One table's constraints and the columns each side names. |
| `triggers` | `rdb$triggers` | Triggers, optionally narrowed to one table. |
| `generators` | `rdb$generators` | Firebird's sequences. The value is read with `GEN_ID(<name>, 0)`, which is a read and not an advance. |
| `domains` | `rdb$fields` | Domains with base type, length, charset, nullability, `DEFAULT` source and check source. |
| `database` | `rdb$database`, `mon$` | Server version and the database's own facts. |

`NAME` is required for `table`, `columns`, `indexes` and `foreign-keys`, and
selects one object for `generators` and `domains`.

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

## Examples

```bash
# The two Firebird-specific families
python -m rhosocial.activerecord.backend.impl.firebird introspect generators
python -m rhosocial.activerecord.backend.impl.firebird introspect domains -o json

# One table in full
python -m rhosocial.activerecord.backend.impl.firebird introspect table orders

# A specific database file
python -m rhosocial.activerecord.backend.impl.firebird introspect tables -d /var/lib/firebird/data/shop.fdb
```
