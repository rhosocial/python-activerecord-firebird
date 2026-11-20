# Firebird-specific execute tests

Namespace for capabilities that only this backend executes. Leaf directories are
database shards: each leaf declares its own database in conftest.py, numbered
from 	est_db_25 upward. This parent holds no test files and no shard.

No backend-unique execute leaf exists yet.
