# Changelog

## [1.0.0.dev1] - 2026-07-01

### Added

- **Async backend**: `AsyncFirebirdBackend` — wraps synchronous `firebird-driver` in a thread pool executor for async/await support
- **Async transaction manager**: `AsyncFirebirdTransactionManager` supporting savepoints
- **Async introspector**: `AsyncFirebirdIntrospector` with thread-pool-based executor
- **Partition DDL**: `FirebirdPartitionMixin` and core `PartitionMixin` added to `FirebirdDialect` MRO (partitioning not supported, raises `UnsupportedFeatureError`)
- **DataType #108**: `FirebirdTypeSupportMixin` added to `FirebirdDialect` MRO; `parsed_data_type` populated in both sync and async introspectors
- **CLI named-migration**: New `named-migration` subcommand with `--async` support
- **CLI helpers**: `add_connection_args()` and `resolve_connection_config_from_args()` in `cli/connection.py`

### Changed

- Bumped version to `1.0.0.dev1`
- `SyncFirebirdIntrospector` rewritten to use new `SyncAbstractIntrospector` base class
- Migrated `cli/__init__.py` to use `importlib.import_module` instead of `__import__`
- Removed duplicate method definitions in `FirebirdDialect`

### Fixed

- `FirebirdDialect` now properly includes `FirebirdTypeSupportMixin` in its MRO
- `FirebirdTableMixin.format_create_table_statement` rejects partition clauses with `UnsupportedFeatureError`
- Sync introspector updated to work with core `feature.named-migration-system` (1.0.0.dev29+)
