# 方言表达式

## Firebird SQL 方言

Firebird 默认使用 SQL 方言 3，提供特定的语法和函数。

## 字符串函数

### 连接

```sql
-- 使用 || 进行字符串连接
SELECT first_name || ' ' || last_name AS full_name FROM users
```

### 字符串操作

```sql
-- 长度
SELECT LENGTH(name) FROM users

-- 子字符串
SELECT SUBSTRING(name FROM 1 FOR 5) FROM users

-- 大小写
SELECT UPPER(name), LOWER(email) FROM users

-- 修剪
SELECT TRIM(name) FROM users
```

## 日期/时间函数

### 当前值

```sql
-- 当前日期
SELECT CURRENT_DATE FROM rdb$database

-- 当前时间
SELECT CURRENT_TIME FROM rdb$database

-- 当前时间戳
SELECT CURRENT_TIMESTAMP FROM rdb$database
```

### 日期算术

```sql
-- 添加天数
SELECT CURRENT_DATE + 7 FROM rdb$database

-- 减去天数
SELECT CURRENT_DATE - 30 FROM rdb$database

-- 天数差
SELECT DATEDIFF(day, start_date, end_date) FROM events
```

## 聚合函数

### 标准聚合

```sql
-- 计数
SELECT COUNT(*) FROM users

-- 求和
SELECT SUM(amount) FROM orders

-- 平均值
SELECT AVG(price) FROM products

-- 最小/最大值
SELECT MIN(created_at), MAX(created_at) FROM events
```

## 窗口函数 (Firebird 3.0+)

### 排名函数

```sql
-- 行号
SELECT ROW_NUMBER() OVER (ORDER BY salary DESC) as rank FROM employees

-- 排名
SELECT RANK() OVER (PARTITION BY department ORDER BY salary DESC) as rank FROM employees

-- 密集排名
SELECT DENSE_RANK() OVER (ORDER BY score DESC) as rank FROM students
```

### 分析函数

```sql
-- Lead/Lag
SELECT 
    name,
    salary,
    LEAD(salary) OVER (ORDER BY salary) as next_salary,
    LAG(salary) OVER (ORDER BY salary) as prev_salary
FROM employees

-- 第一个值
SELECT FIRST_VALUE(name) OVER (ORDER BY salary DESC) as top_earner FROM employees
```

## 公共表表达式 (Firebird 3.0+)

### 简单 CTE

```sql
WITH active_users AS (
    SELECT id, name, email
    FROM users
    WHERE active = 1
)
SELECT * FROM active_users
```

### 递归 CTE

```sql
WITH RECURSIVE org_chart AS (
    -- 基础情况
    SELECT id, name, manager_id, 1 as level
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    -- 递归情况
    SELECT e.id, e.name, e.manager_id, oc.level + 1
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.id
)
SELECT * FROM org_chart
```

## EXECUTE BLOCK

### 匿名 PSQL

```sql
EXECUTE BLOCK AS
DECLARE variable total INTEGER;
BEGIN
    SELECT COUNT(*) INTO total FROM users;
    INSERT INTO stats (count_value) VALUES (total);
END
```

### 带输入参数

```sql
EXECUTE BLOCK (user_id INTEGER = ?) AS
BEGIN
    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id;
END
```

## MERGE 语句 (Firebird 2.1+)

### 更新插入操作

```sql
MERGE INTO target_table t
USING source_table s ON t.id = s.id
WHEN MATCHED THEN
    UPDATE SET t.name = s.name, t.value = s.value
WHEN NOT MATCHED THEN
    INSERT (id, name, value) VALUES (s.id, s.name, s.value)
```

## RETURNING 子句

### 带 RETURNING 的 INSERT

```sql
INSERT INTO users (name, email)
VALUES ('Alice', 'alice@example.com')
RETURNING id, name
```

### 带 RETURNING 的 UPDATE

```sql
UPDATE users
SET name = 'Alice Smith'
WHERE id = 1
RETURNING id, name, email
```

### 带 RETURNING 的 DELETE

```sql
DELETE FROM users
WHERE id = 1
RETURNING name, email
```

## 标识符引号

### 双引号用于标识符

```sql
-- 对于保留字或区分大小写的标识符使用双引号
SELECT "user", "order" FROM "users"

-- 带空格的列名
SELECT "First Name" FROM users
```

## 布尔表达式

### Firebird 3.0+ 布尔支持

```sql
-- 布尔比较
SELECT * FROM users WHERE active = TRUE
SELECT * FROM users WHERE active = FALSE
SELECT * FROM users WHERE NOT active
```

## 条件表达式

### CASE 语句

```sql
SELECT 
    name,
    CASE 
        WHEN age < 18 THEN '未成年'
        WHEN age >= 18 AND age < 65 THEN '成人'
        ELSE '老年'
    END as age_group
FROM users
```

### COALESCE

```sql
SELECT COALESCE(nickname, username, '匿名') as display_name FROM users
```

### NULLIF

```sql
-- 如果值相等则返回 NULL
SELECT NULLIF(quantity, 0) as quantity FROM products
```

💡 *AI 提示:* "如何使用 Firebird 的窗口函数计算累计总和？"