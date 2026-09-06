# EXECUTE BLOCK

## Overview

EXECUTE BLOCK allows executing multiple PSQL statements as a single unit, similar to stored procedures but without requiring explicit creation.

## Basic Syntax

### Simple EXECUTE BLOCK

```sql
EXECUTE BLOCK AS
BEGIN
    -- Statements here
    INSERT INTO audit_log (action, timestamp) VALUES ('LOGIN', CURRENT_TIMESTAMP);
    UPDATE user_stats SET login_count = login_count + 1 WHERE user_id = 1;
END
```

### With Declarations

```sql
EXECUTE BLOCK AS
DECLARE variable total INTEGER;
BEGIN
    SELECT COUNT(*) INTO total FROM users;
    INSERT INTO stats (count_value) VALUES (total);
END
```

## Input Parameters

### Passing Parameters

```sql
EXECUTE BLOCK (user_id INTEGER = ?) AS
BEGIN
    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
    INSERT INTO login_history (user_id, login_time) VALUES (:user_id, CURRENT_TIMESTAMP);
END
```

### Multiple Parameters

```sql
EXECUTE BLOCK (
    user_id INTEGER = ?,
    action VARCHAR(50) = ?
) AS
BEGIN
    INSERT INTO audit_log (user_id, action, timestamp)
    VALUES (:user_id, :action, CURRENT_TIMESTAMP);
END
```

## Output Parameters

### Returning Results

```sql
EXECUTE BLOCK
RETURNS (user_count INTEGER, total_orders INTEGER) AS
BEGIN
    SELECT COUNT(*) INTO user_count FROM users;
    SELECT COUNT(*) INTO total_orders FROM orders;
    SUSPEND;
END
```

## Complex Operations

### Data Migration

```sql
EXECUTE BLOCK AS
DECLARE variable old_id INTEGER;
DECLARE variable new_id INTEGER;
BEGIN
    FOR SELECT id FROM old_table INTO :old_id DO
    BEGIN
        INSERT INTO new_table (name, value)
        SELECT name, value FROM old_table WHERE id = :old_id
        RETURNING id INTO :new_id;
        
        UPDATE related_table SET foreign_id = :new_id WHERE foreign_id = :old_id;
    END
END
```

### Conditional Logic

```sql
EXECUTE BLOCK AS
DECLARE variable user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO user_count FROM users;
    
    IF (user_count < 100) THEN
    BEGIN
        INSERT INTO messages (text) VALUES ('Low user count warning');
    END
    ELSE IF (user_count > 1000) THEN
    BEGIN
        INSERT INTO messages (text) VALUES ('High user count alert');
    END
END
```

### Cursor Operations

```sql
EXECUTE BLOCK AS
DECLARE variable user_name VARCHAR(100);
DECLARE variable user_email VARCHAR(255);
BEGIN
    FOR SELECT name, email FROM users INTO :user_name, :user_email DO
    BEGIN
        INSERT INTO user_backup (name, email, backup_date)
        VALUES (:user_name, :user_email, CURRENT_DATE);
    END
END
```

## Error Handling

### Exception Handling

```sql
EXECUTE BLOCK AS
BEGIN
    BEGIN
        INSERT INTO users (name) VALUES ('Test');
    END
    WHEN ANY DO
    BEGIN
        INSERT INTO error_log (error_message, timestamp)
        VALUES ('Insert failed', CURRENT_TIMESTAMP);
    END
END
```

### Custom Exceptions

```sql
EXECUTE BLOCK AS
DECLARE variable balance DECIMAL(10,2);
BEGIN
    SELECT balance INTO balance FROM accounts WHERE id = 1;
    
    IF (balance < 0) THEN
        EXCEPTION negative_balance 'Balance cannot be negative';
    
    UPDATE accounts SET balance = balance - 100 WHERE id = 1;
END
```

## Python Usage

### Basic Execution

```python
# Simple EXECUTE BLOCK
backend.execute("""
    EXECUTE BLOCK AS
    BEGIN
        INSERT INTO audit_log (action, timestamp) VALUES ('LOGIN', CURRENT_TIMESTAMP);
    END
""")
```

### With Parameters

```python
# EXECUTE BLOCK with parameters
backend.execute("""
    EXECUTE BLOCK (user_id INTEGER = ?) AS
    BEGIN
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
    END
""", (1,))
```

### Complex Operations

```python
# Data processing with EXECUTE BLOCK
backend.execute("""
    EXECUTE BLOCK AS
    DECLARE variable total DECIMAL(10,2);
    BEGIN
        SELECT SUM(amount) INTO total FROM orders WHERE user_id = 1;
        INSERT INTO user_reports (user_id, total_orders, report_date)
        VALUES (1, total, CURRENT_DATE);
    END
""")
```

## Performance Considerations

### When to Use EXECUTE BLOCK

- Multiple related operations
- Complex business logic
- Data transformations
- Conditional operations

### When to Avoid EXECUTE BLOCK

- Simple single statements
- Operations that can be done in application code
- When stored procedures would be more appropriate

## Best Practices

### Keep Blocks Simple

```sql
-- Good: Clear, focused operations
EXECUTE BLOCK AS
BEGIN
    INSERT INTO audit_log (action) VALUES ('LOGIN');
    UPDATE user_stats SET login_count = login_count + 1;
END

-- Avoid: Overly complex blocks
EXECUTE BLOCK AS
-- Too much logic
```

### Use Meaningful Variable Names

```sql
-- Good: Descriptive names
DECLARE variable user_count INTEGER;
DECLARE variable order_total DECIMAL(10,2);

-- Avoid: Cryptic names
DECLARE variable c INTEGER;
DECLARE variable t DECIMAL(10,2);
```

### Handle Exceptions

```sql
-- Always include error handling
EXECUTE BLOCK AS
BEGIN
    -- Operations
EXCEPTION WHEN OTHERS DO
    -- Error handling
END
```

💡 *AI Prompt:* "When should I use EXECUTE BLOCK instead of creating a stored procedure?"