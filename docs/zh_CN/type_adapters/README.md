# 类型适配器

## 概述

类型适配器处理 Python 类型和 Firebird 数据库类型之间的转换。Firebird 后端包含常用数据类型的内置适配器，并支持自定义适配器以满足特殊需求。

## 类型映射

### Firebird 到 Python 类型转换

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

### 内置适配器

#### FirebirdBlobAdapter

处理二进制 BLOB 数据 (SUB_TYPE 0)：

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdBlobAdapter

adapter = FirebirdBlobAdapter()

# Python 到 Firebird
db_value = adapter.to_database(b"binary data", bytes)

# Firebird 到 Python
py_value = adapter.from_database(b"binary data", bytes)
# 返回: b"binary data"
```

#### FirebirdTextBlobAdapter

处理文本 BLOB 数据 (SUB_TYPE 1)：

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdTextBlobAdapter

adapter = FirebirdTextBlobAdapter()

# Python 到 Firebird
db_value = adapter.to_database("text content", str)

# Firebird 到 Python
py_value = adapter.from_database(b"text content", str)
# 返回: "text content"
```

#### FirebirdBooleanAdapter

处理 BOOLEAN 类型 (Firebird 3.0+)：

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdBooleanAdapter

adapter = FirebirdBooleanAdapter()

# Python 到 Firebird（存储为整数 0/1）
db_value = adapter.to_database(True, bool)
# 返回: 1

# Firebird 到 Python
py_value = adapter.from_database(1, bool)
# 返回: True
```

#### FirebirdDecimalAdapter

处理 DECIMAL 和 NUMERIC 类型：

```python
from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdDecimalAdapter

adapter = FirebirdDecimalAdapter()

# Python 到 Firebird
db_value = adapter.to_database(Decimal("123.45"), Decimal)

# Firebird 到 Python
py_value = adapter.from_database(Decimal("123.45"), Decimal)
# 返回: Decimal("123.45")
```

## 自定义适配器

### 创建自定义适配器

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter
from typing import Any, Dict, List, Type, Optional

class CustomEmailAdapter(SQLTypeAdapter):
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {str: [str]}
    
    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        # 验证电子邮件格式
        if "@" not in value:
            raise ValueError(f"无效的电子邮件格式: {value}")
        return value.lower()
    
    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[str]:
        if value is None:
            return None
        return str(value)
```

### 注册自定义适配器

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# 全局注册适配器
FirebirdBackend.register_adapter(CustomEmailAdapter())

# 或为特定后端实例注册
backend = FirebirdBackend(config=config)
backend.register_adapter(CustomEmailAdapter())
```

## 时区处理

### 时间戳配置

Firebird 存储不带时区信息的时间戳。后端可以处理时区转换：

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timezone="America/New_York"  # 设置会话时区
)
```

### UTC 时间戳

```python
from datetime import datetime, timezone

# 存储为 UTC
utc_now = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_now,))

# 检索并转换
result = backend.execute("SELECT created_at FROM events WHERE id = ?", (1,))
local_time = result[0].replace(tzinfo=timezone.utc).astimezone()
```

## 类型转换示例

### 日期和时间类型

```python
from datetime import date, time, datetime

# 日期
backend.execute("INSERT INTO events (event_date) VALUES (?)", (date(2026, 1, 1),))

# 时间
backend.execute("INSERT INTO events (event_time) VALUES (?)", (time(14, 30),))

# 时间戳
backend.execute("INSERT INTO events (event_timestamp) VALUES (?)", 
                (datetime(2026, 1, 1, 14, 30),))
```

### 数值类型

```python
from decimal import Decimal

# Decimal
backend.execute("INSERT INTO products (price) VALUES (?)", (Decimal("19.99"),))

# Float
backend.execute("INSERT INTO measurements (value) VALUES (?)", (3.14159,))
```

### 布尔类型

```python
# 布尔 (Firebird 3.0+)
backend.execute("INSERT INTO settings (enabled) VALUES (?)", (True,))

# 对于旧版 Firebird，使用 CHAR(1) 和 'T'/'F'
backend.execute("INSERT INTO settings (enabled) VALUES (?)", ("T",))
```

💡 *AI 提示:* "如何处理 Firebird 时间戳的时区转换？"