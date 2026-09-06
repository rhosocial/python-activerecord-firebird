# Dialect Expressions

## Firebird SQL Dialect

Firebird uses SQL dialect 3 by default, providing specific syntax and functions.

## String Functions

### Concatenation

```sql
-- Use || for string concatenation
SELECT first_name || ' ' || last_name AS full_name FROM users
```

### String Operations

```sql
-- Length
SELECT LENGTH(name) FROM users

-- Substring
SELECT SUBSTRING(name FROM 1 FOR 5) FROM users

-- Upper/Lower case
SELECT UPPER(name), LOWER(email) FROM users

-- Trim
SELECT TRIM(name) FROM users
```

## Date/Time Functions

### Current Values

```sql
-- Current date
SELECT CURRENT_DATE FROM rdb$database

-- Current time
SELECT CURRENT_TIME FROM rdb$database

-- Current timestamp
SELECT CURRENT_TIMESTAMP FROM rdb$database
```

### Date Arithmetic

```sql
-- Add days
SELECT CURRENT_DATE + 7 FROM rdb$database

-- Subtract days
SELECT CURRENT_DATE - 30 FROM rdb$database

-- Difference in days
SELECT DATEDIFF(day, start_date, end_date) FROM events
```

## Aggregate Functions

### Standard Aggregates

```sql
-- Count
SELECT COUNT(*) FROM users

-- Sum
SELECT SUM(amount) FROM orders

-- Average
SELECT AVG(price) FROM products

-- Min/Max
SELECT MIN(created_at), MAX(created_at) FROM events
```

## Window Functions (Firebird 3.0+)

### Ranking Functions

```sql
-- Row number
SELECT ROW_NUMBER() OVER (ORDER BY salary DESC) as rank FROM employees

-- Rank
SELECT RANK() OVER (PARTITION BY department ORDER BY salary DESC) as rank FROM employees

-- Dense rank
SELECT DENSE_RANK() OVER (ORDER BY score DESC) as rank FROM students
```

### Analytic Functions

```sql
-- Lead/Lag
SELECT 
    name,
    salary,
    LEAD(salary) OVER (ORDER BY salary) as next_salary,
    LAG(salary) OVER (ORDER BY salary) as prev_salary
FROM employees

-- First value
SELECT FIRST_VALUE(name) OVER (ORDER BY salary DESC) as top_earner FROM employees
```

## Common Table Expressions (Firebird 3.0+)

### Simple CTE

```sql
WITH active_users AS (
    SELECT id, name, email
    FROM users
    WHERE active = 1
)
SELECT * FROM active_users
```

### Recursive CTE

```sql
WITH RECURSIVE org_chart AS (
    -- Base case
    SELECT id, name, manager_id, 1 as level
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    -- Recursive case
    SELECT e.id, e.name, e.manager_id, oc.level + 1
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.id
)
SELECT * FROM org_chart
```

## EXECUTE BLOCK

### Anonymous PSQL

```sql
EXECUTE BLOCK AS
DECLARE variable total INTEGER;
BEGIN
    SELECT COUNT(*) INTO total FROM users;
    INSERT INTO stats (count_value) VALUES (total);
END
```

### With Input Parameters

```sql
EXECUTE BLOCK (user_id INTEGER = ?) AS
BEGIN
    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
END
```

## MERGE Statement (Firebird 2.1+)

### Upsert Operation

```sql
MERGE INTO target_table t
USING source_table s ON t.id = s.id
WHEN MATCHED THEN
    UPDATE SET t.name = s.name, t.value = s.value
WHEN NOT MATCHED THEN
    INSERT (id, name, value) VALUES (s.id, s.name, s.value)
```

## RETURNING Clause

### INSERT with RETURNING

```sql
INSERT INTO users (name, email)
VALUES ('Alice', 'alice@example.com')
RETURNING id, name
```

### UPDATE with RETURNING

```sql
UPDATE users
SET name = 'Alice Smith'
WHERE id = 1
RETURNING id, name, email
```

### DELETE with RETURNING

```sql
DELETE FROM users
WHERE id = 1
RETURNING name, email
```

## Identifier Quoting

### Double Quotes for Identifiers

```sql
-- Use double quotes for reserved words or case-sensitive identifiers
SELECT "user", "order" FROM "users"

-- Column names with spaces
SELECT "First Name" FROM users
```

## Boolean Expressions

### Firebird 3.0+ Boolean Support

```sql
-- Boolean comparisons
SELECT * FROM users WHERE active = TRUE
SELECT * FROM users WHERE active = FALSE
SELECT * FROM users WHERE NOT active
```

## Conditional Expressions

### CASE Statement

```sql
SELECT 
    name,
    CASE 
        WHEN age < 18 THEN 'Minor'
        WHEN age >= 18 AND age < 65 THEN 'Adult'
        ELSE 'Senior'
    END as age_group
FROM users
```

### COALESCE

```sql
SELECT COALESCE(nickname, username, 'Anonymous') as display_name FROM users
```

### NULLIF

```sql
-- Return NULL if values are equal
SELECT NULLIF(quantity, 0) as quantity FROM products
```

💡 *AI Prompt:* "How do I use Firebird's window functions for running totals?"