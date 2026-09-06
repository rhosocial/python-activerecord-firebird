# Field Types

## Firebird Data Types

Firebird provides various data types for different storage needs.

## Numeric Types

### Integer Types

| Type | Size | Range |
|------|------|-------|
| SMALLINT | 2 bytes | -32,768 to 32,767 |
| INTEGER | 4 bytes | -2,147,483,648 to 2,147,483,647 |
| BIGINT | 8 bytes | -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807 |

### Floating Point Types

| Type | Size | Precision |
|------|------|-----------|
| FLOAT | 4 bytes | ~7 decimal digits |
| DOUBLE PRECISION | 8 bytes | ~15 decimal digits |

### Decimal Types

| Type | Description |
|------|-------------|
| DECIMAL(p,s) | Exact numeric with precision and scale |
| NUMERIC(p,s) | Similar to DECIMAL |

## String Types

### Variable Length

| Type | Max Size | Description |
|------|----------|-------------|
| VARCHAR(n) | 32,765 bytes | Variable character string |
| CLOB | 2GB | Character Large Object |

### Fixed Length

| Type | Size | Description |
|------|------|-------------|
| CHAR(n) | 1-32,767 bytes | Fixed character string |

## Binary Types

| Type | Description |
|------|-------------|
| BLOB SUB_TYPE 0 | Binary Large Object |
| BLOB SUB_TYPE 1 | Text Large Object |
| BLOB SUB_TYPE 2-7 | Application-defined subtypes |

## Date/Time Types

| Type | Description |
|------|-------------|
| DATE | Calendar date |
| TIME | Time of day |
| TIMESTAMP | Date and time combined |

## Boolean Type

| Type | Description |
|------|-------------|
| BOOLEAN | TRUE/FALSE values (Firebird 3.0+) |

## Special Types

### Arrays

Firebird supports multi-dimensional arrays:

```sql
-- 1D array
column_name INTEGER[10]

-- 2D array
column_name VARCHAR(30)[3,4]
```

### Domains

Reusable column type definitions:

```sql
CREATE DOMAIN EMAIL_ADDRESS AS VARCHAR(255)
NOT NULL
CHECK (VALUE LIKE '%@%.%')
```

## Python Type Mapping

| Firebird Type | Python Type |
|---------------|-------------|
| INTEGER | int |
| BIGINT | int |
| SMALLINT | int |
| FLOAT | float |
| DOUBLE PRECISION | float |
| DECIMAL | Decimal |
| NUMERIC | Decimal |
| VARCHAR | str |
| CHAR | str |
| BLOB | bytes |
| CLOB | str |
| DATE | date |
| TIME | time |
| TIMESTAMP | datetime |
| BOOLEAN | bool |

💡 *AI Prompt:* "When should I use BLOB vs VARCHAR for text storage?"