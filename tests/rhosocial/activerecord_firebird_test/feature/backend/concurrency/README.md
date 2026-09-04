# concurrency

Firebird concurrency tests: the `ConcurrencyAware` protocol implementation (`MON$MAX_CONNECTIONS` connection-limit probe and concurrency hint).

Sync-only: the `firebird-driver` backend does not support asynchronous execution, so no `_async` twin exists (recorded Gap, see plan §4.3).
