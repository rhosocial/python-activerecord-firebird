# Date/time differences: `seconds_between`

Core's `seconds_between(start, end)` node answers one question: how many
seconds elapsed from `start` to `end`. The result is signed (`end - start`
means the end earlier than the start is negative) and fractional, and each
backend spells it with the operation its engine actually has. This page
records Firebird's spelling, its resolution, and the bind order.

## Spelling

Firebird has no interval value to subtract and no `EXTRACT(EPOCH FROM ...)`.
The distance is asked of `DATEDIFF`, whose unit is a keyword of the call:

```sql
(DATEDIFF(MILLISECOND FROM <start> TO <end>) * 0.001)
```

`DATEDIFF(MILLISECOND, ...)` is the finest unit Firebird keeps. A Firebird
timestamp stores four fractional digits -- tenths of a millisecond -- and
`DATEDIFF` with `MILLISECOND` returns `NUMERIC(18, 1)` rather than a whole
`BIGINT`, so no stored digit is dropped. Multiplying the count by `0.001`
converts it to seconds.

`DATEDIFF` is signed by itself, so the rendered `end - start` needs no
`CASE`: a negative result means `end` lies before `start`.

Firebird's numeric `0.001` multiplication is exact and produces four
decimal places (`0.5000`, `0.0001`). Do **not** spell this as a division by
`1000.0`: Firebird derives the result scale from the operands, and
`NUMERIC(18, 1) / NUMERIC(5, 1)` rounds a tenth-millisecond difference to
`0.00`. The multiplication form was measured on Firebird 5.0.4:

| start | end | result |
|---|---|---|
| `2026-06-04 10:00:00.0000` | `2026-06-04 10:00:00.5000` | `0.5000` |
| `2026-06-04 10:00:00.0001` | `2026-06-04 10:00:00.0002` | `0.0001` |
| `2026-06-04 11:00:00.0000` | `2026-06-04 10:00:00.0000` | `-3600.0000` |
| `2026-06-04 10:00:00.0000` | `2026-06-04 10:00:00.0000` | `0.0000` |

## Resolution and rounding

The source resolution is one tenth of a millisecond, and every value
Firebird stores can be represented exactly. Nothing is rounded or truncated
by this spelling. A caller who wants whole seconds rounds the returned
number explicitly, as with every backend's `seconds_between`; the node does
not claim a unit it cannot keep.

The `NUMERIC(18, 1)` intermediate covers the whole Firebird timestamp range
(0001-01-01 through 9999-12-31), and the multiplication result stays within
that range too.

## Bind order and alias

The expression renders `start` first and `end` second, so the bind
parameters are collected in that order:

```python
from datetime import datetime

from rhosocial.activerecord.backend.expression import Literal, seconds_between

start = Literal(dialect, datetime(2026, 6, 4, 10, 0))
end = Literal(dialect, datetime(2026, 6, 4, 11, 0))
expr = seconds_between(dialect, start, end).as_("queue_seconds")
sql, params = expr.to_sql()
# sql:    '(DATEDIFF(MILLISECOND FROM ? TO ?) * 0.001) AS "QUEUE_SECONDS"'
# params: (datetime(2026, 6, 4, 10, 0), datetime(2026, 6, 4, 11, 0))
```

`.as_("...")` is applied through the dialect's `apply_alias`, so the alias
survives whether the node is rendered alone or inside a select list.
Identifiers follow Firebird's folding: an unquoted name is upper-cased and
then quoted (`"QUEUE_SECONDS"`).

## Availability

The formatter uses `DATEDIFF`, which this backend already gates at Firebird
2.5 through `supports_functions()["datediff"]`. On an older server the SQL
is not accepted; the capability answer is the place to check before
constructing the node.
