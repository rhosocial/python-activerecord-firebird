# EXECUTE BLOCK

## 概述

EXECUTE BLOCK 允许将多个 PSQL 语句作为单个单元执行，类似于存储过程，但不需要显式创建。

## 基本语法

### 简单 EXECUTE BLOCK

```sql
EXECUTE BLOCK AS
BEGIN
    -- 此处的语句
    INSERT INTO audit_log (action, timestamp) VALUES ('LOGIN', CURRENT_TIMESTAMP);
    UPDATE user_stats SET login_count = login_count + 1 WHERE user_id = 1;
END
```

### 带声明

```sql
EXECUTE BLOCK AS
DECLARE variable total INTEGER;
BEGIN
    SELECT COUNT(*) INTO total FROM users;
    INSERT INTO stats (count_value) VALUES (total);
END
```

## 输入参数

### 传递参数

```sql
EXECUTE BLOCK (user_id INTEGER = ?) AS
BEGIN
    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
    INSERT INTO login_history (user_id, login_time) VALUES (:user_id, CURRENT_TIMESTAMP);
END
```

### 多个参数

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

## 输出参数

### 返回结果

```sql
EXECUTE BLOCK
RETURNS (user_count INTEGER, total_orders INTEGER) AS
BEGIN
    SELECT COUNT(*) INTO user_count FROM users;
    SELECT COUNT(*) INTO total_orders FROM orders;
    SUSPEND;
END
```

## 复杂操作

### 数据迁移

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

### 条件逻辑

```sql
EXECUTE BLOCK AS
DECLARE variable user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO user_count FROM users;
    
    IF (user_count < 100) THEN
    BEGIN
        INSERT INTO messages (text) VALUES ('低用户数警告');
    END
    ELSE IF (user_count > 1000) THEN
    BEGIN
        INSERT INTO messages (text) VALUES ('高用户数警报');
    END
END
```

### 游标操作

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

## 错误处理

### 异常处理

```sql
EXECUTE BLOCK AS
BEGIN
    BEGIN
        INSERT INTO users (name) VALUES ('测试');
    END
    WHEN ANY DO
    BEGIN
        INSERT INTO error_log (error_message, timestamp)
        VALUES ('插入失败', CURRENT_TIMESTAMP);
    END
END
```

### 自定义异常

```sql
EXECUTE BLOCK AS
DECLARE variable balance DECIMAL(10,2);
BEGIN
    SELECT balance INTO balance FROM accounts WHERE id = 1;
    
    IF (balance < 0) THEN
        EXCEPTION negative_balance '余额不能为负';
    
    UPDATE accounts SET balance = balance - 100 WHERE id = 1;
END
```

## Python 用法

### 基本执行

```python
# 简单 EXECUTE BLOCK
backend.execute("""
    EXECUTE BLOCK AS
    BEGIN
        INSERT INTO audit_log (action, timestamp) VALUES ('LOGIN', CURRENT_TIMESTAMP);
    END
""")
```

### 带参数

```python
# 带参数的 EXECUTE BLOCK
backend.execute("""
    EXECUTE BLOCK (user_id INTEGER = ?) AS
    BEGIN
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
    END
""", (1,))
```

### 复杂操作

```python
# 使用 EXECUTE BLOCK 进行数据处理
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

## 性能考虑

### 何时使用 EXECUTE BLOCK

- 多个相关操作
- 复杂业务逻辑
- 数据转换
- 条件操作

### 何时避免 EXECUTE BLOCK

- 简单的单条语句
- 可以在应用程序代码中完成的操作
- 当存储过程更合适时

## 最佳实践

### 保持块简单

```sql
-- 好：清晰、专注的操作
EXECUTE BLOCK AS
BEGIN
    INSERT INTO audit_log (action) VALUES ('LOGIN');
    UPDATE user_stats SET login_count = login_count + 1;
END

-- 避免：过于复杂的块
EXECUTE BLOCK AS
-- 逻辑太多
```

### 使用有意义的变量名

```sql
-- 好：描述性名称
DECLARE variable user_count INTEGER;
DECLARE variable order_total DECIMAL(10,2);

-- 避免：神秘的名称
DECLARE variable c INTEGER;
DECLARE variable t DECIMAL(10,2);
```

### 处理异常

```sql
-- 始终包含错误处理
EXECUTE BLOCK AS
BEGIN
    -- 操作
EXCEPTION WHEN OTHERS DO
    -- 错误处理
END
```

💡 *AI 提示:* "何时应使用 EXECUTE BLOCK 而不是创建存储过程？"