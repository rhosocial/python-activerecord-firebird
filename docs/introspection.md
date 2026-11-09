# Database Introspection

The Firebird backend answers what the database declares (from the `RDB$` catalogue), what its own object families contain (generators, domains, exceptions, routines, roles, privileges, charsets, collations, publications, dependency edges), and what a table's rows hold (three data families). `backend.introspector` is the entry point for all three, and every answer on this page is Firebird's own: what this engine says about the database file it opened, not the shape a cross-dialect consumer can expect.

## Overview

The introspection system is available via `backend.introspector` and answers:

- **Database information**: the attachment's file path and the server version the dialect was adapted to
- **Table information**: tables, views, external tables and both kinds of global temporary table
- **Column information**: name, position, nullability, default, and a type composed from `RDB$FIELDS`
- **Index information**: name, uniqueness, primary-key flag and column order
- **Foreign-key information**: referenced relation, column mapping, and the rules the catalogue declares
- **Trigger information**: timing, events and source
- **View information**: the definition, plus the relations the compiled `BLR` reads
- **Firebird's own families**: generators with their values, domains, exceptions, procedures and their parameters, functions and their arguments, constraints, roles, privileges, charsets, collations, publications
- **Dependency edges**: `RDB$DEPENDENCIES`, in both directions
- **Data answers**: per-column profiles, value listings, and two columns' domain overlap

There is exactly one namespace per database file and it has no name. A caller who asks for a schema is refused rather than answered for the whole database, because "the database you named does not exist here" and "here is everything" are different answers.

## What Firebird Answers

This backend declares twenty-five probes on its introspection mixin; a probe is a question about the server in front of you rather than about the product. Of the twenty-five, twenty-three answer `True` unconditionally, `table_storage` answers `False` unconditionally, and `publications` answers `True` from Firebird 4.0.0 and `False` below it -- or on a dialect that has not been adapted. Read the `False` rows first: a probe that answers `False` says the question cannot be asked of this server, never that the answer was empty or zero.

| Probe | Firebird answers | The question it gates |
|-------|------------------|-----------------------|
| `supports_introspection()` | `True` | Anything about the schema at all |
| `supports_database_info()` | `True` | The database file this attachment opened |
| `supports_table_introspection()` | `True` | Tables, views, external and temporary relations |
| `supports_column_introspection()` | `True` | Columns and what they declare |
| `supports_index_introspection()` | `True` | Indexes, their columns and uniqueness |
| `supports_foreign_key_introspection()` | `True` | Foreign keys and their rules |
| `supports_view_introspection()` | `True` | Views and their definitions |
| `supports_trigger_introspection()` | `True` | Triggers, timing, events and source |
| `supports_table_storage_introspection()` | `False` | Per-table storage bytes |
| `supports_column_data_profile()` | `True` | What each column of a table holds |
| `supports_column_value_sample()` | `True` | Which values occur, and how often |
| `supports_join_coverage()` | `True` | How much two columns' domains overlap |
| `supports_domain_introspection()` | `True` | Domains, Firebird's reusable type layer |
| `supports_generator_introspection()` | `True` | Generators (sequences), with their values |
| `supports_exception_introspection()` | `True` | Named PSQL messages |
| `supports_procedure_introspection()` | `True` | Procedures and their parameter lists |
| `supports_function_introspection()` | `True` | PSQL functions and legacy UDFs alike |
| `supports_constraint_introspection()` | `True` | Every constraint kind, `NOT NULL` rows included |
| `supports_role_introspection()` | `True` | Roles |
| `supports_privilege_introspection()` | `True` | SQL and system grants |
| `supports_charset_introspection()` | `True` | Character sets |
| `supports_collation_introspection()` | `True` | Collations, keyed to their character set |
| `supports_dependency_introspection()` | `True` | `RDB$DEPENDENCIES`, one edge per row |
| `supports_view_relation_introspection()` | `True` | The relations a view reads, with its contexts |
| `supports_publication_introspection()` | `True` from Firebird 4.0.0 | Logical-replication publications |

The families beyond core's set are this backend's own: core has no probe for domains, generators, exceptions, routines, roles, privileges, charsets, collations, publication lists or view relations, so each carries its own switch and each CLI type is gated on it. A `True` promises only that the query renders and the server accepts it; it says nothing about the shape of the answer or its price, and the price of every family is stated where the family is described.

`supports_table_storage_introspection()` is the one constant `False`. The `RDB$` relations that mention pages describe the database file, not the objects in it; a per-relation page count is what the external `gstat` tool produces, not a catalogue question. So the family answers `False` and the storage slots of a table record stay `None`, rather than an empty answer that would read as storage of zero.

`supports_publication_introspection()` is the one version gate. `RDB$PUBLICATIONS` does not exist before Firebird 4, so asking an older server would be a `-204` relation-unknown rather than an empty list. The probe reads the dialect's version and answers `False` when no version has been confirmed -- an unadapted dialect does not raise mid-probe; it declines. The CLI adapts the dialect first, so the answer is about the server in front of it.

### Left False by Inheritance

The families core defines but this backend does not answer stay on the base mixin's `False`. Where the CLI offers the family -- the four operational types -- a run is refused at the gate (exit 2) rather than reaching an empty listing. Where it does not, the absence is deliberate: `ddl` has no CLI type because its capability is permanently `False`, while `object dependencies`, `partitions` and `extensions` have no stable answer to model here.

| Family | Probe | Why |
|--------|-------|-----|
| `unused-indexes` | `supports_unused_indexes_detection()` | Firebird keeps no per-index access counter |
| `table-stats` | `supports_table_stats()` | No per-table I/O counter relation |
| `runtime` | `supports_runtime_stats()` | No live runtime measurement relation |
| `index-stats` | `supports_index_stats()` | The same missing per-index counters |
| `ddl` | `supports_ddl_extraction()` | Firebird records a source body, not a rebuildable `CREATE` |
| object dependencies | `supports_object_dependencies()` | The catalogue's shape is not this family's; see [Dependency Edges](#dependency-edges) |
| partitions | `supports_partition_info()` | Firebird has no partitioned tables |
| extensions | `supports_extensions()` | No add-on component catalogue is mapped |

The distinction that matters is between `False` and an empty answer. A `False` tells a caller not to ask; an empty list would tell it the question was asked and nothing was found. An operator reading "no unused indexes" for an engine that keeps no such counter would be reading a report nobody produced.

The probes do not test grants. If the connected user may not read a relation, the engine's own error arrives at execution; the probe answered about the server, not about this user's privileges.

### Engine Objects With No Family

These are real catalogue objects, or real engine absences, that this backend does not answer for. They are listed rather than offered as empty CLI types: an offered family that always returns nothing reads as "the database has none".

| Object | Catalogue | Why there is no family |
|--------|-----------|------------------------|
| `types` | none; domains live in `RDB$FIELDS` | Firebird has no standalone user-defined type. Domains *are* its reusable type layer, and `domains` already answers them; a second `types` family would duplicate the same rows under another name. |
| Table partitioning | none | Firebird 5 and 6 have no partitioned tables; `supports_partition_info()` is `False` and the mixin refuses every partition clause. |
| Tablespaces | none | Firebird has no tablespace object. Its file objects (`RDB$FILES`) describe secondary and shadow files, not a table's storage placement. |
| `packages` | `RDB$PACKAGES` | The relation exists and Firebird 5's language reference documents `CREATE PACKAGE`, but this backend's measured probe recorded `CREATE PACKAGE` refused on 5.0.4 and the 6.0.0 server, so the relation is treated as reserved. This is a contradiction worth re-measuring before a family is added. |
| `filters` | `RDB$FILTERS` | `DECLARE FILTER` is a real schema object (a declared BLOB converter); no family answers it. |
| `auth-mappings` | `RDB$AUTH_MAPPING` | An authentication mapping is instance/security configuration, not a table-scoped schema object. |
| `publication-tables` | `RDB$PUBLICATION_TABLES` | The `publications` family answers the publication, not the tables each publication replicates. |
| `security-classes` | `RDB$SECURITY_CLASSES` | Access-control lists. The `privileges` family already answers grants; a class listing was not requested and is not model material. |
| `array-dimensions` | `RDB$FIELD_DIMENSIONS` | Array bounds are part of a column's declaration; the column family composes the type from `RDB$FIELDS` and does not expose per-dimension bounds. |
| `db-creators` | `RDB$DB_CREATORS` | A grant in the security database, not a schema object of this database. |
| engine lookups | `RDB$TIME_ZONES`, `RDB$TYPES`, `RDB$KEYWORDS` | Engine-owned lookup tables (time zones from Firebird 4), not user objects. |
| status material | `RDB$PAGES`, `RDB$FILES`, `RDB$FORMATS`, `RDB$TRANSACTIONS`, `RDB$CONFIG`, `RDB$BACKUP_HISTORY`, `RDB$LOG_FILES` | File/runtime state rather than schema; the `status` introspector and the declined statistical families answer what can be answered. |

The rule is the same as for the families above: a type is added when the engine backs a stable, model-relevant answer, not to make the catalogue look complete. Each absent object here has an owning relation, and each would get a typed result and its own probe rather than a generic bag that hides what the engine guarantees.

## Basic Usage

### Accessing the Introspector

```python
from rhosocial.activerecord.backend.impl.firebird.backend.backend import FirebirdBackend

backend = FirebirdBackend(
    host="localhost",
    port=3050,
    database="/path/to/test_db",
    username="SYSDBA",
    password="secret",
)
backend.connect()
# Several formatters read the dialect's version, so adapt before asking.
backend.introspect_and_adapt()

introspector = backend.introspector
```

### Sync and async

The async backend exposes the same method names, awaited:

```python
from rhosocial.activerecord.backend.impl.firebird.backend.async_backend import (
    AsyncFirebirdBackend,
)

backend = AsyncFirebirdBackend(database="/path/to/test_db", username="SYSDBA")
await backend.connect()
await backend.introspect_and_adapt()

tables = await backend.introspector.list_tables()
```

`FirebirdIntrospector` and `AsyncFirebirdIntrospector` are separate classes that cannot coexist; they share every question and every parser, so a record has the same shape on both sides. Adaptation is part of answering, not setup: `value-samples` renders a row bound that differs by version, and asking an unadapted dialect for it raises rather than guessing a floor.

### Cache Management

Answers are cached by scope, and Firebird's own families share the core scopes with an `extra` discriminator (a generator listing and a domain listing both live under `SCHEMA`, for example):

```python
backend.introspector.clear_cache()

from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE, name="ORDERS")
```

### The Namespace

Every formatter calls the dialect's namespace check first. `schema=None` and `schema=""` both mean "the whole database"; any other value raises `UnsupportedFeatureError` with a message saying the whole database is the only scope. The CLI therefore passes `schema=None` everywhere.

## Catalogue Families

Each of these is a read of `RDB$` relations or of `MON$DATABASE`; none of them scans the user's rows.

| Family | Method | Firebird source |
|--------|--------|-----------------|
| Database | `get_database_info()` | `MON$DATABASE` |
| Tables | `list_tables()` | `RDB$RELATIONS` |
| Columns | `list_columns()` | `RDB$RELATION_FIELDS` joined to `RDB$FIELDS` |
| Indexes | `list_indexes()` | `RDB$INDICES`, `RDB$INDEX_SEGMENTS` |
| Foreign keys | `list_foreign_keys()` | `RDB$REF_CONSTRAINTS`, `RDB$RELATION_CONSTRAINTS` |
| Triggers | `list_triggers()` | `RDB$TRIGGERS` |
| Views | `list_views()`, `get_view_info()` | `RDB$RELATIONS`, `RDB$VIEW_SOURCE` |
| Generators | `list_generators()`, `get_generator_info()` | `RDB$GENERATORS` + `GEN_ID(name, 0)`, joined to `RDB$RELATION_FIELDS` for identity ownership |
| Domains | `list_domains()`, `get_domain_info()` | `RDB$FIELDS` |
| Exceptions | `list_exceptions()`, `get_exception_info()` | `RDB$EXCEPTIONS` |
| Procedures | `list_procedures()`, `get_procedure_info()` | `RDB$PROCEDURES` |
| Procedure parameters | `list_procedure_parameters()` | the procedure parameters relation |
| Functions | `list_functions()`, `get_function_info()` | `RDB$FUNCTIONS` |
| Function arguments | `list_function_arguments()` | the function arguments relation |
| Constraints | `list_constraints()` | `RDB$RELATION_CONSTRAINTS` |
| Roles | `list_roles()` | `RDB$ROLES` |
| Privileges | `list_privileges()` | `RDB$USER_PRIVILEGES` |
| Charsets | `list_charsets()` | `RDB$CHARACTER_SETS` |
| Collations | `list_collations()` | `RDB$COLLATIONS` |
| Dependencies | `list_dependencies()` | `RDB$DEPENDENCIES` |
| View relations | `list_view_relations()` | `RDB$VIEW_RELATIONS` |
| Publications | `list_publications()` | `RDB$PUBLICATIONS`, from Firebird 4 |

### Tables and Views

The listing projects `RDB$RELATION_NAME`, `RDB$VIEW_BLR` and `RDB$RELATION_TYPE`, from `RDB$RELATIONS`, ordered by name. `RDB$SYSTEM_FLAG = 0` drops the catalogue's own relations unless `include_system=True`; `RDB$VIEW_BLR` is what tells a view from a table, and `RDB$RELATION_TYPE` is projected because Firebird's global temporary tables are ordinary user relations -- nothing else in the row betrays them.

The kind mapping is the catalogue's own five values: `0` persistent table, `1` view, `2` external table, `4` connection-level GTT (`ON COMMIT PRESERVE ROWS`), `5` transaction-level GTT (`ON COMMIT DELETE ROWS`). Both GTT kinds read as `TEMPORARY`; what separates them is the `ON COMMIT` clause, not the kind of relation. Firebird has no materialized views, so none is reported. A row with an unrecognised kind falls back to `VIEW` when it carries a `RDB$VIEW_BLR` and to `BASE_TABLE` otherwise.

An explicit `table_type` narrows the kind: `VIEW` selects rows with a `RDB$VIEW_BLR`, `TABLE` and `BASE TABLE` select rows without one. A spelling that is neither adds no condition, so it answers with every relation rather than none.

A view's definition comes from `RDB$VIEW_SOURCE`, and `view-relations` answers what the compiled `BLR` actually read: one row per relation the view uses, with `RDB$VIEW_CONTEXT` (the number the `BLR` uses for it) and `RDB$CONTEXT_NAME` (the alias the view's `SELECT` gave it). Neither is recoverable from the source text once it is written.

### Columns

The question joins `RDB$RELATION_FIELDS` to `RDB$FIELDS` through `RDB$FIELD_SOURCE`, so each column carries both its per-column facts and the domain it was declared from. The type string is composed from the catalogue: `BLOB` keeps its `SUB_TYPE` word, `VARCHAR` and `CHAR` carry their character length, and the remainder is parsed by the dialect. `data_type` is the lower-cased spelling and `data_type_full` the composed one.

`nullable` is `NULL_FLAG IS NULL` -- Firebird records nullability by the absence of a flag. `comment` is read from `RDB$DESCRIPTION`; `collation` stays `None` because the catalogue gives an id rather than a name and the question does not resolve it.

An identity column is reported as `is_auto_increment=True` from `RDB$RELATION_FIELDS.RDB$IDENTITY_TYPE` (`NULL` means "not identity", `0` is `GENERATED ALWAYS`, `1` is `GENERATED BY DEFAULT`), with the raw code, the generation mode and the backing `RDB$GENERATOR_NAME` in `extra`. That is the generator-to-column ownership link for model inference: a system generator and the column it fills are named by the same row. A computed column is `is_generated=True` with its declaration in `generated_expression`, read from `RDB$COMPUTED_SOURCE`. Both facts were projected by the column question before the parser read them; a caller could not tell an identity key from an ordinary one.

**The relation name is a bind value, not an identifier.** The column question keeps the caller's spelling verbatim, while the catalogue stores unquoted names folded to upper case. A table created with an unquoted `orders` is stored as `ORDERS`, so passing the lower-case `"orders"` gets an empty column list, which reads exactly like a table with no columns. Pass the catalogue's spelling, or read it from `list_tables()` first. The profile family folds the name itself before asking, precisely because an empty profile would otherwise be indistinguishable from a table that has no columns.

### Indexes, Foreign Keys and Constraints

The index listing reads `RDB$INDICES` with `RDB$INDEX_SEGMENTS` for the column order, and is joined to the constraint catalogue so each index can say which kind it is. `is_unique` comes from `UNIQUE_FLAG`; `is_primary` is read from the constraint type first, and only falls back to the generated name (`RDB$PRIMARYn`) because a user-named primary key carries no such word. `index_type` is `UNKNOWN` -- Firebird's catalogue names no access method. `is_descending` is reported as `False` for every column: the column is not read from the catalogue, so a descending index is not distinguished here.

The foreign-key listing reads `RDB$REF_CONSTRAINTS` with `RDB$RELATION_CONSTRAINTS`, resolving the referenced relation and the column mapping, plus the update and delete rules the catalogue spells.

`constraints` is a broader question than either: `RDB$RELATION_CONSTRAINTS` holds every kind, including the `NOT NULL` rows Firebird records as constraints. It can be narrowed to one table or one kind (the CLI's `--constraint-type`).

### Triggers

`RDB$TRIGGERS` carries the timing, the events and the source, so a trigger record answers when it fires, on what, and what it runs. The listing can be narrowed to one table.

### Generators and Domains

A generator is Firebird's sequence, and its value is not in the catalogue: `RDB$GENERATORS` names them and `GEN_ID(<name>, 0)` reads one. A generator name cannot be bound as a parameter, so the catalogue read and the value reads cannot be one statement: `list_generators()` issues one `GEN_ID` per generator. The result is cached, so the cost is paid once per cache generation rather than once per call. `get_generator_info()` answers from the user list first and only falls back to `include_system=True` for a name that list does not contain, which keeps a user lookup from paying the system generators' `GEN_ID` calls.

From Firebird 3.0 the listing also answers *which column a generator backs*. `RDB$RELATION_FIELDS.RDB$GENERATOR_NAME` names the internal generator of an identity column, so the listing LEFT joins that relation and projects `owner_table`, `owner_column` and `identity_type`. The join is left deliberately: a user-created generator has no owning column, and an inner join would delete every plain sequence. Below 3.0 the catalogue has no such column, so the ownership fields are not projected and stay `None` rather than producing a `-206 column unknown`.

A domain is Firebird's reusable type layer, and `RDB$FIELDS` answers the same question a column's type descriptor does. `list_domains()` and `get_domain_info()` follow the same user-first, system-second lookup as generators.

### Exceptions, Routines, Roles and Privileges

`exceptions` lists named PSQL messages from `RDB$EXCEPTIONS`; procedures come from `RDB$PROCEDURES` with their signature, and their parameters from the procedure parameters relation, inputs first then outputs; functions come from `RDB$FUNCTIONS`, which lists PSQL functions and legacy UDFs alike, with their arguments including the return slot. Procedure parameters and function arguments are separate relations from the routines they belong to, which is why they are separate families and separate CLI types rather than fields of the routine record.

`roles` lists `RDB$ROLES`; `privileges` lists grants from `RDB$USER_PRIVILEGES`, which holds SQL and system grants in one place, and can be narrowed by object and by grantee.

### Charsets, Collations and Publications

`charsets` lists `RDB$CHARACTER_SETS`; `collations` lists `RDB$COLLATIONS`, keyed to its character set by id, and can be narrowed to one character set. `publications` lists logical-replication publications from `RDB$PUBLICATIONS` -- name, owner, active flag, auto-enable flag and system flag -- and only on Firebird 4 or later.

### Dependency Edges

`RDB$DEPENDENCIES` records one edge per row, in one direction: what depends on what. The listing projects `RDB$DEPENDENT_NAME`, `RDB$DEPENDENT_TYPE`, `RDB$DEPENDED_ON_NAME`, `RDB$DEPENDED_ON_TYPE` and `RDB$FIELD_NAME`, ordered by both names. Naming one object narrows the answer to the edges where it appears on **either** side, because "what does this depend on" and "what depends on this" are the same table read in opposite directions, and a caller inspecting one object wants both.

This family is **its own**, gated on `supports_dependency_introspection()` and offered by the CLI as `rdb-dependencies`, rather than core's `object-dependencies` family. The reason is the row shape, not a preference: core's dependency parser reads `referenced_name` or `referenced` for the far end of the edge, while `RDB$DEPENDENCIES` spells that column `RDB$DEPENDED_ON_NAME` and this backend projects it as `DEPENDED_ON_NAME`. A row from this catalogue has no `referenced` key at all, so core's parser would skip every edge (`if not dependent or not referenced: continue`) and report a dependency graph with no edges. Two different shapes are two families; pointing the common switch at this catalogue would have answered a question whose answer cannot be expressed. `supports_object_dependencies()` therefore stays `False`, and the CLI type is spelled after the relation it reads.

The record also carries the field-level edge (`field_name`) and no `kind` or `action`: the catalogue records direction and object types, not the drop behaviour core's `ObjectDependency` models.

## Operational Families

None of the four answers. Each probe is `False` by inheritance, the CLI refuses the type (exit 2), and no query is run.

| Family | Probe | Why this backend declines |
|--------|-------|---------------------------|
| `unused-indexes` | `supports_unused_indexes_detection()` | Firebird keeps no per-index access counter |
| `table-stats` | `supports_table_stats()` | No per-table I/O counter relation |
| `runtime` | `supports_runtime_stats()` | No live runtime measurement relation |
| `index-stats` | `supports_index_stats()` | The same missing per-index counters |

Firebird has no statistics collector and no `RDB$` relation standing in for one, so there is no counter view whose window could be dated. The CLI offers these four rather than omitting them because "this engine cannot tell you" is a fact worth letting a caller ask for and be told -- but it is told as a refusal, not as an empty listing.

## DDL Extraction

DDL extraction is not offered by this backend's CLI. `supports_ddl_extraction()` is `False` because Firebird records a source body, not a rebuildable `CREATE` statement: the text that would recreate a table with its constraints, defaults and computed expressions is not retained anywhere the catalogue exposes, and this backend does not assemble one. An assembled fragment would read as authoritative while being this library's guess, so the type is not advertised. The backend keeps `format_ddl_statement_query_statement` and the `DDLStatement` expression so a future real implementation can reuse them, but the CLI does not offer a type whose capability is permanently `False`.

## Data Families

The three data families measure the rows rather than read a catalogue. Firebird keeps no per-column statistics catalogue at all -- `RDB$FIELDS` describes what a column *declares*, and `SET STATISTICS` maintains an index's selectivity for the optimiser without publishing a per-column distribution -- so every figure is computed when asked, exact, and paid for in time proportional to the table.

| Family | Method | Price |
|--------|--------|-------|
| Column profiles | `list_column_data_profiles(table)` | One aggregate over the table, every column at once |
| Value samples | `sample_column_values(table, column, limit=100)` | One grouped pass over the column, plus a sort |
| Join coverage | `estimate_join_coverage(left_table, left_column, right_table, right_column)` | Each side read twice, in both directions |

### Column Profiles

The profile is **one `SELECT` projecting every column at once**, not one `UNION ALL` arm per column, and the difference is Firebird's. A union has to reconcile one type per column position across every arm, and `min_value` carrying an `INTEGER` from one column and a `VARCHAR` from another has no common type this engine will accept -- the arms would have to be cast to a common text type, which is a bound truncation waiting to happen and a type the caller then has to parse back. A single projection keeps each column's own bounds type, and it is still one read of the table.

The slots are positional (`c1_`, `c2_`, ...) and the catalogue's own names travel as text labels beside them: a Firebird identifier is folded to upper case and limited to 63 characters, so a result name cannot carry an arbitrary column name and a name the engine folded would not match the caller's spelling. The rendered shape, for a two-column table whose second column is a `BLOB`:

```sql
SELECT CAST('ID' AS VARCHAR(63)) AS "C1_NAME",
       CAST(SUM(CASE WHEN "ID" IS NULL THEN 1 ELSE 0 END) AS DECIMAL(18,2)) AS "C1_NULL_COUNT",
       COUNT(DISTINCT "ID") AS "C1_DISTINCT_COUNT",
       MIN("ID") AS "C1_MIN",
       MAX("ID") AS "C1_MAX",
       CAST('DOC' AS VARCHAR(63)) AS "C2_NAME",
       CAST(SUM(CASE WHEN "DOC" IS NULL THEN 1 ELSE 0 END) AS DECIMAL(18,2)) AS "C2_NULL_COUNT",
       CAST(NULL AS VARCHAR(1)) AS "C2_DISTINCT_COUNT",
       CAST(NULL AS VARCHAR(1)) AS "C2_MIN",
       CAST(NULL AS VARCHAR(1)) AS "C2_MAX",
       COUNT(*) AS "ROW_COUNT",
       CAST('aggregate' AS VARCHAR(9)) AS "SOURCE"
FROM "ORDERS"
```

The parser pivots that one wide row back into one record per column -- `column_name`, `null_count`, `distinct_count`, `min_value`, `max_value`, `row_count`, `source` -- and the per-column rules (what `None` means, how `null_fraction` is derived, that a row without a column name is skipped) stay in core's parser rather than being re-implemented here. The result names are written in upper case and quoted, so they come back exactly as spelled; the parser lower-cases the row's keys before handing them on.

An empty table answers `null_fraction = None` because `SUM` over no rows is `NULL` -- absence of a measurement, not "no nulls". `source` is projected into the row as the constant `'aggregate'`, not stamped on afterwards, so a consumer comparing profiles across engines can tell exact from estimated.

**`BLOB` columns are the trap.** `MIN`, `MAX` and `COUNT(DISTINCT ...)` are refused by Firebird at prepare time on a `BLOB`, because these values are not comparable. The introspector therefore reads the column catalogue first -- not only for the names, but for each declared type -- and tells the formatter which columns are opaque; a column whose declared type starts with `BLOB` gets its distinct count and both bounds projected as `CAST(NULL AS VARCHAR(1))`. The row is kept: its null count and the table's row count are still measured, and dropping the column would delete the one signal this family exists to deliver, while asking for all five figures would make the server reject the whole query. So a `None` in `distinct_count`, `min_value` or `max_value` here is a **real answer about the type**, not a missing measurement -- it means "this engine will not measure that about this column", and it is distinguishable from a zero the engine measured. The CLI says so on stderr, naming the columns, because a reader seeing nulls in a table would otherwise read them as zeroes.

The fixtures for this trap look like this:

```sql
CREATE TABLE intro_profile_orders (
    id INTEGER NOT NULL PRIMARY KEY,
    code VARCHAR(8) NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    note VARCHAR(8),
    doc BLOB SUB_TYPE TEXT
)
```

`note` and `doc` are declared plain rather than `NULL`: **Firebird has no explicit nullability constraint keyword**, and rejects the `NULL` token. A live test whose DDL wrote it was rejected; write the absence of `NOT NULL` instead.

### Value Samples

A `GROUP BY` over the column plus a sort of the groups: the same order of cost as the profile, which is why the two are separate calls. `ORDER BY COUNT(*) DESC` is what makes the answer "the most frequent values" rather than "the first values", and ties break by the value so two runs of the same query agree.

The row bound goes through the dialect's own `LIMIT`/`OFFSET` renderer, which spells `FETCH NEXT ... ROWS ONLY` from Firebird 3 and `ROWS m TO n` before it. Writing either word into this family would pin it to a version floor the backend does not otherwise impose, and the caller's integer stays a bind parameter rather than being spliced into statement text.

`GROUP BY` groups `NULL`s, so a column containing them has an entry whose `value` is `None`; the parser keeps it, because `NULL` is a legitimate member of a column's domain. A `BLOB` column cannot be grouped: the server refuses the statement rather than answering a shorter list, and the probe's `True` says the family exists, not that every column type can be sampled.

### Join Coverage

One statement produces both fractions, hanging off `RDB$DATABASE` -- the one-row relation this backend uses wherever a projection needs a `FROM`, because Firebird has no `SELECT` without one. For each side, the numerator counts the distinct values of that column which also occur on the other side, under an `IN` predicate over the other side's non-`NULL` values; the denominator counts that side's distinct non-`NULL` values.

`IS NOT NULL` is written on both halves: in the numerator it says what the predicate means, since a value list made of `NULL`s matches nothing; in the divisor `COUNT(DISTINCT ...)` skips `NULL` on its own, but the share is of the values that could join. `NULLIF(..., 0)` makes a column with nothing to match answer `NULL` rather than `0`, so "nothing matched" and "nothing to match" stay distinct.

The `* 1.0` is load-bearing here rather than decorative: Firebird's `/` over two integer counts is integer arithmetic, so three quarters would answer zero. Multiplying first makes one operand floating-point and the fraction is the fraction. Collations are not reconciled -- Firebird compares the two columns under whichever collation applies -- so across mismatched collations the fractions are a lower bound, never an upper one.

```python
profiles = backend.introspector.list_column_data_profiles("ORDERS")
for profile in profiles:
    print(profile.column_name, profile.null_fraction, profile.distinct_count,
          profile.min_value, profile.max_value, profile.row_count)

samples = backend.introspector.sample_column_values("ORDERS", "STATUS", limit=20)
for sample in samples:
    print(sample.value, sample.count)    # value is None when NULL is a group

coverage = backend.introspector.estimate_join_coverage(
    "ORDERS", "CUSTOMER_ID",
    "CUSTOMERS", "ID",
)
print(coverage.left_coverage, coverage.right_coverage)
```

## What Is Verified

This backend's live suite runs against real Firebird servers in CI, not against a rendered string. The workflow starts a `firebirdsql/firebird` container per matrix leg -- Firebird 5 and Firebird 6-snapshot -- writes the scenario configuration the fixtures read, and runs the whole `tests/` tree against it (`-n auto`). The data-family tests create a hundred-row table with hand-counted expectations and compare every figure against them, including the `BLOB` column's `None` slots and the `NULL` rows in the value listing. Those statements are therefore proven against the servers in the matrix, not merely reviewed.

Two limits on that claim:

- The matrix has no Firebird 4 or earlier leg, so the `publications` gate's `False` branch is pinned by unit tests against a simulated version rather than exercised against a pre-4 server. Its `True` branch runs live on both legs, which are newer than 4.
- The families this backend declines are not exercised against a server at all: there is no statement to run. Their correctness is the `False` itself, and the CLI tests pin the refusal.

## Version and Availability Floors

Only one family has a version floor, and it is a floor on the relation's existence rather than on a query feature.

| Family | Floor | What a missing floor looks like |
|--------|-------|---------------------------------|
| `publications` | Firebird 4.0.0, where `RDB$PUBLICATIONS` arrives | probe `False`; CLI exits 2 without running the query |
| `value-samples` row bound | Firebird 3.0 for `FETCH NEXT`, `ROWS m TO n` before | not a gate: the dialect renders both spellings |
| every other family | none established here | - |

The floor is checked with `version_at_least((4, 0, 0))`, which never raises and answers `False` when no version has been confirmed -- a capability nobody confirmed is not claimed. On an older server the statement would render and the server would answer `-204`, relation unknown; the probe is what keeps the CLI from reaching that error. The CLI calls `backend.introspect_and_adapt()` before the gate for exactly this family, so the answer is about the attached server rather than about the newest release this backend knows.

A probe answering `False` is "the question cannot be asked here", not "nothing was used". It does not say that no index was used or that the database has no publications: it says the server cannot be asked. `False` lets a caller take its fallback knowingly; the empty list is reserved for a question that was asked and had nothing to report.

## Command Line Introspection

The backend provides a command-line surface over the same introspector: twenty-nine types -- twenty-two catalogue families, the four operational families it declines, and the three data families.

```bash
python -m rhosocial.activerecord.backend.impl.firebird introspect tables \
  --database /path/to/test_db
```

`--database` is required. Connection parameters can come from the flags or the environment.

| Parameter | Environment Variable | Description |
|-----------|---------------------|-------------|
| `--host` | `FIREBIRD_HOST` | Host (default: `localhost`) |
| `--port` | `FIREBIRD_PORT` | Port (default: 3050) |
| `--database` | `FIREBIRD_DATABASE` | Database path (required) |
| `--user` | `FIREBIRD_USER` | Username |
| `--password` | `FIREBIRD_PASSWORD` | Password |
| `--charset` | `FIREBIRD_CHARSET` | Connection character set (default: `UTF8`) |
| `--role` | `FIREBIRD_ROLE` | SQL role |
| `--ssl` | `FIREBIRD_SSL` | SSL mode |

### Introspection Types

The largest surface of the nine backends, because each `RDB$` relation that answers independently gets its own type and no type covers two.

| Type | Description | Name | Flags it reads |
|------|-------------|------|----------------|
| `tables` | Tables, views, external and temporary relations | refused | `--include-system` |
| `views` | List all views, or describe one | optional (view) | - |
| `columns` | Column information | required (table) | - |
| `indexes` | Index information | required (table) | - |
| `foreign-keys` | Foreign-key information | required (table) | - |
| `triggers` | Triggers, optionally of one table | optional (table) | - |
| `database` | The database file this attachment opened | refused | - |
| `generators` | Generators with their current values | optional (generator) | - |
| `domains` | Domains | optional (domain) | - |
| `exceptions` | Named PSQL messages | optional (exception) | `--include-system` |
| `procedures` | Procedures and their signatures | optional (procedure) | `--include-system` |
| `procedure-parameters` | One procedure's parameters, inputs then outputs | required (procedure) | - |
| `functions` | PSQL functions and legacy UDFs | optional (function) | `--include-system` |
| `function-arguments` | One function's arguments, return slot included | required (function) | - |
| `constraints` | Constraints of every kind | optional (table) | `--constraint-type` |
| `roles` | Roles | refused | `--include-system` |
| `privileges` | Grants | refused | `--object`, `--grantee` |
| `charsets` | Character sets | refused | - |
| `collations` | Collations, optionally of one character set | optional (charset) | - |
| `rdb-dependencies` | `RDB$DEPENDENCIES` edges, either direction | optional (object) | - |
| `view-relations` | The relations a view reads | optional (view) | - |
| `publications` | Publications, Firebird 4 and later | refused | `--include-system` |
| `unused-indexes` | Declined: `False` | refused | - |
| `table-stats` | Declined: `False` | refused | - |
| `runtime` | Declined: `False` | refused | - |
| `index-stats` | Declined: `False` | refused | - |
| `column-profiles` | What each column of a table holds, `source='aggregate'` | required (table) | - |
| `value-samples` | Most frequent values of one column | required (table) | `--column` |
| `join-coverage` | Overlap of two columns' value domains | required (left table) | `--column`, `--right-table`, `--right-column` |

The advertised list is derived from the same capability map the handler consults, so a family cannot be answerable and unaskable at once. A type whose switch is `False` on the connected server is refused when handled (exit 2) rather than run and answered with an empty list. A `NAME` a type cannot use is refused (exit 2) rather than ignored, and a required one that is missing exits 1 -- a typo and a misfiled question are different failures. Where a name selects one member (`views`, `generators`, `domains`, `exceptions`, `procedures`, `functions`), a name that matches nothing exits 1; where it is a filter (`constraints`, `collations`, `rdb-dependencies`, `view-relations`), an empty listing is a real answer.

There is no `--limit` flag on this parser: `value-samples` always asks with the introspector signature's own default (`VALUE_SAMPLE_LIMIT`, 100). A run that does not name a limit must not send one, and the helper that forwards it exists so the day the flag arrives it is forwarded in one place rather than written into both branches.

### Querying Firebird's Own Families

```bash
python -m rhosocial.activerecord.backend.impl.firebird introspect generators \
  --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect domains POSITIVE_INT \
  --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect constraints ORDERS \
  --constraint-type "PRIMARY KEY" --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect privileges \
  --object ORDERS --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect rdb-dependencies ORDERS \
  --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect publications \
  --include-system --database /path/to/test_db
```

### Querying the Declined and Data Families

```bash
# Declined families: exit 2, no query run
python -m rhosocial.activerecord.backend.impl.firebird introspect unused-indexes \
  --database /path/to/test_db

# The data families
python -m rhosocial.activerecord.backend.impl.firebird introspect column-profiles ORDERS \
  --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect value-samples ORDERS \
  --column STATUS --database /path/to/test_db
python -m rhosocial.activerecord.backend.impl.firebird introspect join-coverage ORDERS \
  --column CUSTOMER_ID --right-table CUSTOMERS --right-column ID \
  --database /path/to/test_db
```

`column-profiles` prints a note on stderr naming any column whose distinct count and bounds were not measured -- a `BLOB`'s figures are `None` in the rows themselves, and the note keeps a reader from mistaking the nulls for zeroes. The note is on stderr so `json`, `csv` and `tsv` stay parseable.

### Output Formats and Async Mode

```bash
python -m rhosocial.activerecord.backend.impl.firebird introspect tables \
  --database /path/to/test_db --output json
python -m rhosocial.activerecord.backend.impl.firebird introspect tables \
  --database /path/to/test_db --output csv
python -m rhosocial.activerecord.backend.impl.firebird introspect tables \
  --database /path/to/test_db --output tsv
```

`table` is the default. `--async` exists for surface parity with the sibling backends and is **refused** (exit 1): the official `firebird-driver` has no asynchronous support, and this command does not silently degrade to a synchronous run that would look asynchronous to the caller. The async backend and introspector exist for programmatic use; the CLI flag does not.

## API Reference

### Introspection Methods

| Method | Description |
|--------|-------------|
| `get_database_info()` | The attached database file |
| `list_tables(schema=None, include_system=False, table_type=None)` | Relations with their kind |
| `get_table_info(name, schema=None)` | One table with columns, indexes and foreign keys |
| `table_exists(name, schema=None)` | Whether the relation is listed |
| `list_columns(table_name, schema=None)` | Column declarations, with the composed type |
| `get_column_info(table_name, column_name, schema=None)` | One column |
| `get_primary_key(table_name, schema=None)` | The primary-key index |
| `list_indexes(table_name, schema=None)` | Indexes with their columns |
| `list_foreign_keys(table_name, schema=None)` | Foreign keys with their rules |
| `list_triggers(table_name=None, schema=None)` | Triggers, optionally of one table |
| `list_views(schema=None, include_system=False)`, `get_view_info(name, schema=None)` | Views |
| `list_generators(include_system=False)`, `get_generator_info(name)` | Generators with their values |
| `list_domains(include_system=False)`, `get_domain_info(name)` | Domains |
| `list_exceptions(include_system=False)`, `get_exception_info(name)` | Exceptions |
| `list_procedures(include_system=False, include_source=False)` | Procedures and signatures |
| `list_procedure_parameters(procedure_name)` | One procedure's parameters |
| `list_functions(include_system=False, include_source=False)` | Functions |
| `list_function_arguments(function_name)` | One function's arguments |
| `list_constraints(table_name=None, constraint_type=None, include_system=False)` | Constraints of every kind |
| `list_roles(include_system=False)` | Roles |
| `list_privileges(object_name=None, user_name=None, include_system=False)` | Grants |
| `list_charsets()` | Character sets |
| `list_collations(charset_name=None)` | Collations |
| `list_dependencies(object_name=None)` | Dependency edges, either direction |
| `list_view_relations(view_name=None)` | Relations a view reads |
| `list_publications(include_system=False)` | Publications (Firebird 4+) |
| `list_column_data_profiles(table_name, schema=None)` | What each column holds |
| `sample_column_values(table_name, column_name, limit=100, schema=None)` | Most frequent values |
| `estimate_join_coverage(left_table, left_column, right_table, right_column, schema=None)` | Both coverage fractions |
| `clear_cache()` | Clear all cached answers |
| `invalidate_cache(scope, ...)` | Invalidate one scope, or one name |

The operational families' methods exist on the base introspector and are refused by this dialect's probes; check the probe before calling, and let the `False` be the answer. `get_ddl_statement()` is likewise on the base introspector and `supports_ddl_extraction()` is `False`, so the CLI does not offer a `ddl` type.
