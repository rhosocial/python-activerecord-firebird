# tests/rhosocial/activerecord_firebird_test/feature/logging/conftest.py
"""The logging tests are unit-level: this directory needs no database.

The cases here drive the backend through fake connections and cursors, so
they run without a live Firebird server.  The shared suite has no ``logging``
fixture group, so there is nothing to import and no ``prepare`` /
``teardown`` contract to declare: the directory needs neither a database nor
the per-directory pinning that comes with one.
"""
