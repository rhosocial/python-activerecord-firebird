# 字段类型

## Firebird 数据类型

Firebird 提供多种数据类型，用于不同的存储需求。

## 数值类型

### 整数类型

| 类型 | 大小 | 范围 |
|------|------|------|
| SMALLINT | 2 字节 | -32,768 到 32,767 |
| INTEGER | 4 字节 | -2,147,483,648 到 2,147,483,647 |
| BIGINT | 8 字节 | -9,223,372,036,854,775,808 到 9,223,372,036,854,775,807 |

### 浮点类型

| 类型 | 大小 | 精度 |
|------|------|------|
| FLOAT | 4 字节 | ~7 位十进制数字 |
| DOUBLE PRECISION | 8 字节 | ~15 位十进制数字 |

### 十进制类型

| 类型 | 描述 |
|------|------|
| DECIMAL(p,s) | 带精度和标度的精确数值 |
| NUMERIC(p,s) | 类似 DECIMAL |

## 字符串类型

### 变长类型

| 类型 | 最大大小 | 描述 |
|------|----------|------|
| VARCHAR(n) | 32,765 字节 | 变长字符字符串 |
| CLOB | 2GB | 字符大对象 |

### 固定长度类型

| 类型 | 大小 | 描述 |
|------|------|------|
| CHAR(n) | 1-32,767 字节 | 固定字符字符串 |

## 二进制类型

| 类型 | 描述 |
|------|------|
| BLOB SUB_TYPE 0 | 二进制大对象 |
| BLOB SUB_TYPE 1 | 文本大对象 |
| BLOB SUB_TYPE 2-7 | 应用程序定义的子类型 |

## 日期/时间类型

| 类型 | 描述 |
|------|------|
| DATE | 日历日期 |
| TIME | 一天中的时间 |
| TIMESTAMP | 日期和时间的组合 |

## 布尔类型

| 类型 | 描述 |
|------|------|
| BOOLEAN | TRUE/FALSE 值 (Firebird 3.0+) |

## 特殊类型

### 数组

Firebird 支持多维数组：

```sql
-- 一维数组
column_name INTEGER[10]

-- 二维数组
column_name VARCHAR(30)[3,4]
```

### 域

可重用的列类型定义：

```sql
CREATE DOMAIN EMAIL_ADDRESS AS VARCHAR(255)
NOT NULL
CHECK (VALUE LIKE '%@%.%')
```

## Python 类型映射

| Firebird 类型 | Python 类型 |
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

💡 *AI 提示:* "何时应使用 BLOB 而不是 VARCHAR 存储文本？"