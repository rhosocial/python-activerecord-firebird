# Indexing

## Overview

Firebird supports various index types for optimizing query performance.

## Standard Indexes

### Creating Indexes

```sql
-- Basic index
CREATE INDEX idx_users_email ON users (email)

-- Unique index
CREATE UNIQUE INDEX idx_users_username ON users (username)

-- Composite index
CREATE INDEX idx_users_name_email ON users (name, email)
```

### Index Options

```sql
-- Ascending index (default)
CREATE INDEX idx_users_created ON users (created_at ASC)

-- Descending index
CREATE INDEX idx_users_created_desc ON users (created_at DESC)
```

## Expression Indexes

### Function-based Indexes

```sql
-- Index on function result
CREATE INDEX idx_users_lower_email ON users (LOWER(email))

-- Index on concatenation
CREATE INDEX idx_users_full_name ON users (first_name || ' ' || last_name)
```

## Index Management

### Viewing Indexes

```sql
-- List all indexes for a table
SELECT rdb/index_name, rdb/field_name
FROM rdb$indices i
JOIN rdb$index_segments s ON i.rdb$index_name = s.rdb$index_name
WHERE i.rdb$relation_name = 'USERS'
```

### Dropping Indexes

```sql
-- Drop index
DROP INDEX idx_users_email

-- Drop if exists
DROP INDEX IF EXISTS idx_users_email
```

## Index Best Practices

### When to Create Indexes

- Columns used in WHERE clauses
- Columns used in JOIN conditions
- Columns used in ORDER BY
- Columns with high cardinality

### When to Avoid Indexes

- Small tables
- Columns with low cardinality
- Frequently updated columns
- Columns rarely used in queries

## Index Monitoring

### Check Index Usage

```sql
-- Monitor index usage
SELECT * FROM mon$records
WHERE mon$record_name = 'INDEX'
```

### Index Statistics

```sql
-- Get index statistics
SELECT 
    i.rdb$index_name,
    s.rdb$field_name,
    i.rdb$unique_flag
FROM rdb$indices i
JOIN rdb$index_segments s ON i.rdb$index_name = s.rdb$index_name
WHERE i.rdb$relation_name = 'USERS'
```

## Performance Considerations

### Index Selectivity

```sql
-- High selectivity (good for indexing)
SELECT COUNT(DISTINCT email) / COUNT(*) FROM users

-- Low selectivity (bad for indexing)
SELECT COUNT(DISTINCT gender) / COUNT(*) FROM users
```

### Index Size

```sql
-- Monitor index size
SELECT 
    rdb$index_name,
    rdb$segments
FROM rdb$indices
WHERE rdb$relation_name = 'USERS'
```

💡 *AI Prompt:* "How do I determine which columns need indexes in Firebird?"