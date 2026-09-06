# EXPLAIN

## Overview

Firebird provides EXPLAIN for analyzing query execution plans.

## Basic Usage

### EXPLAIN Statement

```sql
-- Get execution plan
EXPLAIN SELECT * FROM users WHERE email = 'alice@example.com'

-- With JOIN
EXPLAIN SELECT u.name, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.active = 1
```

### Reading Execution Plans

The EXPLAIN output shows:

- **Table scans**: Sequential vs index scans
- **Join methods**: Nested loop, hash join
- **Sort operations**: In-memory vs disk
- **Row estimates**: Expected vs actual rows

## Example Output

```sql
EXPLAIN SELECT * FROM users WHERE email LIKE '%@example.com%'

-- Output might look like:
-- TABLE USERS
--   SCANNED ROWS: 1000
--   FILTER: USERS.EMAIL LIKE '%@example.com%'
--   SORT: NONE
--   ESTIMATED ROWS: 50
```

## Performance Analysis

### Identify Full Table Scans

```sql
-- Look for SCANNED ROWS without index usage
EXPLAIN SELECT * FROM large_table WHERE non_indexed_column = 'value'
```

### Analyze JOIN Performance

```sql
-- Check join order and methods
EXPLAIN SELECT u.name, o.amount
FROM users u
JOIN orders o ON u.id = o.user_id
JOIN products p ON o.product_id = p.id
```

### Check Sort Operations

```sql
-- Identify expensive sorts
EXPLAIN SELECT * FROM users ORDER BY created_at DESC
```

## Using EXPLAIN in Python

```python
# Get execution plan
result = backend.execute("EXPLAIN SELECT * FROM users WHERE email = ?", ('test@example.com',))
print(result)

# Analyze multiple queries
queries = [
    "SELECT * FROM users WHERE id = 1",
    "SELECT * FROM users WHERE email LIKE '%@example.com%'",
    "SELECT u.*, o.* FROM users u JOIN orders o ON u.id = o.user_id"
]

for query in queries:
    plan = backend.execute(f"EXPLAIN {query}")
    print(f"Query: {query[:50]}...")
    print(f"Plan: {plan}")
    print()
```

## Optimization Tips

### Add Missing Indexes

```sql
-- If EXPLAIN shows full table scan
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com'
-- If output shows SCANNED ROWS: 10000, consider adding index:
CREATE INDEX idx_users_email ON users (email)
```

### Rewrite Queries

```sql
-- Instead of:
SELECT * FROM users WHERE YEAR(created_at) = 2026

-- Use:
SELECT * FROM users WHERE created_at >= '2026-01-01' AND created_at < '2027-01-01'
```

### Optimize JOINs

```sql
-- Ensure join columns are indexed
CREATE INDEX idx_orders_user_id ON orders (user_id)
CREATE INDEX idx_orders_product_id ON orders (product_id)
```

## Common EXPLAIN Patterns

### Good Plan Indicators

- Index usage (IDX_*)
- Low row estimates
- Efficient join order

### Bad Plan Indicators

- Full table scans on large tables
- High row estimates
- Expensive sort operations

💡 *AI Prompt:* "How do I interpret Firebird EXPLAIN output for query optimization?"