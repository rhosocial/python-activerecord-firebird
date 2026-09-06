# Introspection

## Overview

Firebird provides metadata queries for inspecting database schema and structure.

## Listing Tables

### System Catalogs

```sql
-- List all user tables
SELECT rdb$relation_name
FROM rdb$relations
WHERE rdb$system_flag = 0
ORDER BY rdb$relation_name
```

### Using INFORMATION_SCHEMA

```sql
-- List tables (Firebird 3.0+)
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'CURRENT_USER'
ORDER BY table_name
```

## Table Structure

### Column Information

```sql
-- Get column details for a table
SELECT 
    rf.rdb$field_name,
    f.rdb$field_type,
    f.rdb$field_length,
    f.rdb$field_sub_type,
    rf.rdb$default_value
FROM rdb$relation_fields rf
JOIN rdb$fields f ON rf.rdb$field_source = f.rdb$field_name
WHERE rf.rdb$relation_name = 'USERS'
ORDER BY rf.rdb$field_position
```

### Field Types

```sql
-- Get field type names
SELECT 
    rf.rdb$field_name,
    CASE f.rdb$field_type
        WHEN 7 THEN 'SMALLINT'
        WHEN 8 THEN 'INTEGER'
        WHEN 10 THEN 'FLOAT'
        WHEN 12 THEN 'DATE'
        WHEN 13 THEN 'TIME'
        WHEN 14 THEN 'CHAR'
        WHEN 16 THEN 'BIGINT'
        WHEN 27 THEN 'DOUBLE'
        WHEN 35 THEN 'TIMESTAMP'
        WHEN 37 THEN 'VARCHAR'
        WHEN 261 THEN 'BLOB'
        ELSE 'UNKNOWN'
    END as field_type_name
FROM rdb$relation_fields rf
JOIN rdb$fields f ON rf.rdb$field_source = f.rdb$field_name
WHERE rf.rdb$relation_name = 'USERS'
ORDER BY rf.rdb$field_position
```

## Index Information

### List Indexes

```sql
-- Get indexes for a table
SELECT 
    i.rdb$index_name,
    s.rdb$field_name,
    i.rdb$unique_flag
FROM rdb$indices i
JOIN rdb$index_segments s ON i.rdb$index_name = s.rdb$index_name
WHERE i.rdb$relation_name = 'USERS'
ORDER BY i.rdb$index_name
```

### Index Details

```sql
-- Get detailed index information
SELECT 
    i.rdb$index_name,
    i.rdb$relation_name,
    i.rdb$unique_flag,
    i.rdb$index_type
FROM rdb$indices i
WHERE i.rdb$relation_name = 'USERS'
```

## Foreign Keys

### List Foreign Keys

```sql
-- Get foreign keys for a table
SELECT 
    rc.rdb$constraint_name,
    rc.rdb$constraint_type,
    rc.rdb$table_name,
    rc.rdb$constraint_name
FROM rdb$relation_constraints rc
WHERE rc.rdb$relation_name = 'USERS'
AND rc.rdb$constraint_type = 'FOREIGN KEY'
```

### Foreign Key Details

```sql
-- Get foreign key column mappings
SELECT 
    rc.rdb$constraint_name,
    s1.rdb$field_name as source_column,
    s2.rdb$field_name as referenced_column,
    rc.rdb$relation_name as referenced_table
FROM rdb$relation_constraints rc
JOIN rdb$index_segments s1 ON rc.rdb$index_name = s1.rdb$index_name
JOIN rdb$ref_constraints refc ON rc.rdb$constraint_name = refc.rdb$constraint_name
JOIN rdb$relation_constraints rc2 ON refc.rdb$const_name_uq = rc2.rdb$constraint_name
JOIN rdb$index_segments s2 ON rc2.rdb$index_name = s2.rdb$index_name
WHERE rc.rdb$relation_name = 'USERS'
```

## Views

### List Views

```sql
-- List all views
SELECT rdb$relation_name
FROM rdb$relations
WHERE rdb$relation_type = 1  -- 1 = view
AND rdb$system_flag = 0
ORDER BY rdb$relation_name
```

### View Definition

```sql
-- Get view source
SELECT rdb$view_source
FROM rdb$relations
WHERE rdb$relation_name = 'ACTIVE_USERS'
```

## Stored Procedures

### List Procedures

```sql
-- List all stored procedures
SELECT rdb$procedure_name
FROM rdb$procedures
WHERE rdb$system_flag = 0
ORDER BY rdb$procedure_name
```

### Procedure Parameters

```sql
-- Get procedure parameters
SELECT 
    p.rdb$parameter_name,
    p.rdb$parameter_type,  -- 0 = input, 1 = output
    f.rdb$field_type,
    f.rdb$field_length
FROM rdb$procedure_parameters p
JOIN rdb$fields f ON p.rdb$field_source = f.rdb$field_name
WHERE p.rdb$procedure_name = 'GET_USER_STATS'
ORDER BY p.rdb$parameter_number
```

## Triggers

### List Triggers

```sql
-- List all triggers
SELECT rdb$trigger_name
FROM rdb$triggers
WHERE rdb$system_flag = 0
ORDER BY rdb$trigger_name
```

### Trigger Details

```sql
-- Get trigger details
SELECT 
    rdb$trigger_name,
    rdb$relation_name,
    rdb$trigger_type,  -- 1 = before, 2 = after
    rdb$trigger_inactive
FROM rdb$triggers
WHERE rdb$relation_name = 'USERS'
```

## Generators (Sequences)

### List Generators

```sql
-- List all generators
SELECT rdb$generator_name
FROM rdb$generators
WHERE rdb$system_flag = 0
ORDER BY rdb$generator_name
```

### Generator Values

```sql
-- Get current generator value
SELECT GEN_ID(generator_name, 0) FROM rdb$database
```

## Python Introspection

### Using the Backend

```python
# List tables
tables = backend.introspect.tables()

# Get table columns
columns = backend.introspect.columns("users")

# Get table indexes
indexes = backend.introspect.indexes("users")

# Get foreign keys
fk = backend.introspect.foreign_keys("users")
```

### Custom Introspection Queries

```python
# Execute custom metadata query
result = backend.execute("""
    SELECT rdb$relation_name
    FROM rdb$relations
    WHERE rdb$system_flag = 0
    ORDER BY rdb$relation_name
""")
tables = [row[0] for row in result]
```

💡 *AI Prompt:* "How do I list all columns and their data types for a Firebird table?"