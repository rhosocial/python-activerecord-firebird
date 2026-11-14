# Firebird backend test shards

Every directory under `execute/` is a database shard: its `conftest.py`
registers one name with `providers.shards.register`, and the root
`tests/conftest.py` pins its items to `xdist_group("db:<name>")`. A directory
runs serially; directories run in parallel under `--dist=loadgroup`.

Directories under `construct/` are IO-free and register nothing.

| Directory | Database |
|---|---|
| `execute/connection` | `test_db_1` |
| `execute/crud` | `test_db_2` |
| `execute/query` | `test_db_3` |
| `execute/join` | `test_db_4` |
| `execute/transaction` | `test_db_5` |
| `execute/ddl_table` | `test_db_6` |
| `execute/ddl_column` | `test_db_7` |
| `execute/ddl_constraint` | `test_db_8` |
| `execute/ddl_index` | `test_db_9` |
| `execute/ddl_view` | `test_db_10` |
| `execute/dml_insert` | `test_db_11` |
| `execute/dml_update_delete` | `test_db_12` |
| `execute/json` | `test_db_13` |
| `execute/partition` | `test_db_14` |
| `execute/introspection` | `test_db_15` |
| `execute/errors` | `test_db_16` |
| `execute/concurrency` | `test_db_17` |
| `execute/cli` | `test_db_18` |
| `execute/functions` | `test_db_19` |
| `execute/sequence_identity` | `test_db_20` |
| `execute/fulltext_spatial` | `test_db_21` |
| `execute/show_admin` | `test_db_22` |
| `execute/routine_domain` | `test_db_23` |

## Backend-specific leaves

Firebird-unique execution capabilities live under
`execute/firebird/<feature>/`. Each leaf directory is a shard and declares its
own database in `conftest.py`, numbered from `test_db_25` upward. The
`execute/firebird/` parent is a namespace only: it holds no test files and no
shard. No leaf exists yet.

`test_db_24` is intentionally unused: backend-unique execution lives under the
`execute/firebird/` namespace instead of a canonical shared directory, and its
leaves start at `test_db_25`.

Backend-unique construction cases live under `construct/firebird/<feature>/`
and allocate no database.
