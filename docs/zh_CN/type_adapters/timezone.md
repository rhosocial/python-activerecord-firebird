# 时区处理

## 概述

Firebird 存储不带时区信息的时间戳。后端提供时区转换支持。

## 配置

### 设置会话时区

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

### 常见时区

| 时区 | 描述 |
|------|------|
| `UTC` | 协调世界时 |
| `America/New_York` | 东部时间 |
| `America/Chicago` | 中部时间 |
| `America/Denver` | 山地时间 |
| `America/Los_Angeles` | 太平洋时间 |
| `Europe/London` | 格林威治标准时间 |
| `Europe/Paris` | 中欧时间 |
| `Asia/Tokyo` | 日本标准时间 |

## 时区转换

### 存储 UTC 时间戳

```python
from datetime import datetime, timezone

# 存储为 UTC
utc_now = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_now,))
```

### 检索本地时间戳

```python
from datetime import datetime, timezone

# 检索并转换
result = backend.execute("SELECT created_at FROM events WHERE id = ?", (1,))
local_time = result[0].replace(tzinfo=timezone.utc).astimezone()
```

### 在时区之间转换

```python
from datetime import datetime, timezone, timedelta

# 从 UTC 转换到本地
utc_time = datetime.now(timezone.utc)
eastern = timezone(timedelta(hours=-5))
local_time = utc_time.astimezone(eastern)
```

## Python 示例

### 基本时区操作

```python
from datetime import datetime, timezone, timedelta

# 创建 UTC 时间戳
utc_time = datetime.now(timezone.utc)

# 转换到不同时区
eastern = timezone(timedelta(hours=-5))
pacific = timezone(timedelta(hours=-8))

eastern_time = utc_time.astimezone(eastern)
pacific_time = utc_time.astimezone(pacific)

print(f"UTC: {utc_time}")
print(f"东部时间: {eastern_time}")
print(f"太平洋时间: {pacific_time}")
```

### 数据库操作

```python
# 存储 UTC 时间戳
utc_now = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_now,))

# 检索并转换
result = backend.execute("SELECT created_at FROM events WHERE id = 1")
stored_time = result[0][0]

# 转换到本地时区
if stored_time.tzinfo is None:
    stored_time = stored_time.replace(tzinfo=timezone.utc)
local_time = stored_time.astimezone(eastern)
```

### 时区感知查询

```python
# 带时区转换的查询
backend.execute("""
    INSERT INTO events (created_at, timezone)
    VALUES (?, ?)
""", (datetime.now(timezone.utc), "America/New_York"))

# 带时区检索
result = backend.execute("""
    SELECT created_at, timezone FROM events WHERE id = 1
""")
```

## 最佳实践

### 存储 UTC

```python
# 好：存储 UTC
utc_time = datetime.now(timezone.utc)
backend.execute("INSERT INTO events (created_at) VALUES (?)", (utc_time,))

# 避免：存储本地时间
local_time = datetime.now()  # 无时区信息
backend.execute("INSERT INTO events (created_at) VALUES (?)", (local_time,))
```

### 显示时转换

```python
# 好：显示时转换
result = backend.execute("SELECT created_at FROM events WHERE id = 1")
utc_time = result[0][0].replace(tzinfo=timezone.utc)
local_time = utc_time.astimezone(eastern)
print(f"事件时间: {local_time}")

# 避免：存储转换后的时间
backend.execute("INSERT INTO events (created_at) VALUES (?)", (local_time,))
```

### 处理夏令时

```python
from datetime import datetime, timezone, timedelta
import pytz

# 使用 pytz 处理夏令时
eastern = pytz.timezone('America/New_York')
utc_time = datetime.now(timezone.utc)
eastern_time = utc_time.astimezone(eastern)

# 处理夏令时转换
try:
    eastern_time.normalize(eastern_time)
except pytz.exceptions.AmbiguousTimeError:
    # 处理模糊时间（夏令时转换）
    pass
```

## 常见问题

### 时区感知与朴素

```python
from datetime import datetime, timezone

# 时区感知
aware_time = datetime.now(timezone.utc)

# 朴素（无时区）
naive_time = datetime.now()

# 无法比较
try:
    if aware_time > naive_time:
        pass
except TypeError as e:
    print(f"无法比较: {e}")
```

### 缺少时区

```python
# 处理缺少的时区
result = backend.execute("SELECT created_at FROM events WHERE id = 1")
stored_time = result[0][0]

if stored_time.tzinfo is None:
    # 假设为 UTC
    stored_time = stored_time.replace(tzinfo=timezone.utc)

local_time = stored_time.astimezone(eastern)
```

## 高级用法

### 自定义时区适配器

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter
from datetime import datetime, timezone

class TimezoneAdapter(SQLTypeAdapter):
    def __init__(self, target_timezone):
        self.target_timezone = target_timezone
    
    @property
    def supported_types(self):
        return {datetime: [datetime]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.target_timezone)

# 注册适配器
FirebirdBackend.register_adapter(TimezoneAdapter(eastern))
```

### 时区转换函数

```python
def convert_timezone(backend, table, column, from_tz, to_tz):
    """转换数据库列中的时区。"""
    backend.execute(f"""
        UPDATE {table}
        SET {column} = {column} AT TIME ZONE ?
    """, (to_tz,))
```

💡 *AI 提示:* "如何处理 Firebird 时间戳的时区转换？"