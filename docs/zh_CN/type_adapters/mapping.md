# 类型映射

## Firebird 到 Python 类型转换

| Firebird 类型 | Python 类型 | 适配器 |
|---------------|-------------|--------|
| INTEGER | int | 默认 |
| BIGINT | int | 默认 |
| SMALLINT | int | 默认 |
| FLOAT | float | 默认 |
| DOUBLE PRECISION | float | 默认 |
| DECIMAL(p,s) | Decimal | FirebirdDecimalAdapter |
| NUMERIC(p,s) | Decimal | FirebirdDecimalAdapter |
| VARCHAR(n) | str | 默认 |
| CHAR(n) | str | 默认 |
| BLOB SUB_TYPE 0 | bytes | FirebirdBlobAdapter |
| BLOB SUB_TYPE 1 | str | FirebirdTextBlobAdapter |
| DATE | date | 默认 |
| TIME | time | 默认 |
| TIMESTAMP | datetime | 默认 |
| BOOLEAN | bool | FirebirdBooleanAdapter |

## 详细映射

### 数值类型

| Firebird 类型 | Python 类型 | 备注 |
|---------------|-------------|------|
| SMALLINT | int | -32,768 到 32,767 |
| INTEGER | int | -2,147,483,648 到 2,147,483,647 |
| BIGINT | int | -9,223,372,036,854,775,808 到 9,223,372,036,854,775,807 |
| FLOAT | float | ~7 位十进制数字 |
| DOUBLE PRECISION | float | ~15 位十进制数字 |
| DECIMAL(p,s) | Decimal | 精确精度 |
| NUMERIC(p,s) | Decimal | 精确精度 |

### 字符串类型

| Firebird 类型 | Python 类型 | 备注 |
|---------------|-------------|------|
| VARCHAR(n) | str | 变长 |
| CHAR(n) | str | 固定长度 |
| BLOB SUB_TYPE 1 | str | 文本 BLOB |
| CLOB | str | 字符大对象 |

### 二进制类型

| Firebird 类型 | Python 类型 | 备注 |
|---------------|-------------|------|
| BLOB SUB_TYPE 0 | bytes | 二进制 BLOB |
| BLOB SUB_TYPE 2-7 | bytes | 应用程序定义 |

### 日期/时间类型

| Firebird 类型 | Python 类型 | 备注 |
|---------------|-------------|------|
| DATE | date | 日历日期 |
| TIME | time | 一天中的时间 |
| TIMESTAMP | datetime | 日期和时间 |

### 布尔类型

| Firebird 类型 | Python 类型 | 备注 |
|---------------|-------------|------|
| BOOLEAN | bool | TRUE/FALSE (Firebird 3.0+) |

## 类型转换示例

### 数值转换

```python
from decimal import Decimal

# 整数
value = 42
db_value = value  # 无需转换

# Decimal
value = Decimal("123.45")
db_value = value  # 无需转换

# 浮点数
value = 3.14159
db_value = value  # 无需转换
```

### 字符串转换

```python
# 字符串
value = "Hello, World!"
db_value = value  # 无需转换

# Unicode
value = "测试"
db_value = value  # 无需转换
```

### 二进制转换

```python
# 字节
value = b"binary data"
db_value = value  # 无需转换

# bytearray
value = bytearray(b"binary data")
db_value = bytes(value)  # 转换为字节
```

### 日期/时间转换

```python
from datetime import date, time, datetime

# 日期
value = date(2026, 1, 1)
db_value = value  # 无需转换

# 时间
value = time(14, 30)
db_value = value  # 无需转换

# 日期时间
value = datetime(2026, 1, 1, 14, 30)
db_value = value  # 无需转换
```

### 布尔转换

```python
# 布尔
value = True
db_value = 1  # 转换为整数用于 Firebird

value = False
db_value = 0  # 转换为整数用于 Firebird
```

## 自定义类型映射

### 定义自定义映射

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

class CustomEmailAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {str: [str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        return value.lower()
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        return str(value)

# 注册自定义适配器
FirebirdBackend.register_adapter(CustomEmailAdapter())
```

### 使用自定义映射

```python
# 自动使用自定义映射
backend.execute("INSERT INTO users (email) VALUES (?)", ("TEST@EXAMPLE.COM",))
result = backend.execute("SELECT email FROM users WHERE id = 1")
# result[0][0] 是 "test@example.com"
```

## 类型验证

### 验证输入

```python
def validate_email(value):
    if "@" not in value:
        raise ValueError(f"无效的电子邮件: {value}")
    return value.lower()

# 在适配器中使用
class EmailAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return validate_email(value)
```

### 验证输出

```python
def validate_date(value):
    if value is None:
        return None
    if not isinstance(value, date):
        raise ValueError(f"无效的日期: {value}")
    return value

# 在适配器中使用
class DateAdapter(SQLTypeAdapter):
    def from_database(self, value, target_type, options=None):
        return validate_date(value)
```

💡 *AI 提示:* "如何在 Firebird 中处理自定义数据类型？"