# 自定义类型适配器

## 概述

自定义类型适配器允许您注册 Python 和数据库值之间的自定义转换器。

## 创建自定义适配器

### 基本适配器

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

### 带选项的适配器

```python
class FirebirdCurrencyAdapter(SQLTypeAdapter):
    def __init__(self, decimal_places=2):
        self.decimal_places = decimal_places
    
    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Decimal: [Decimal, float, int, str]}
    
    def to_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        return round(value, self.decimal_places)
    
    def from_database(self, value: Any, target_type: Type, options: Optional[Dict] = None) -> Optional[Decimal]:
        if value is None:
            return None
        return Decimal(str(value))
```

## 注册适配器

### 全局注册

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# 全局注册
FirebirdBackend.register_adapter(CustomEmailAdapter())
FirebirdBackend.register_adapter(FirebirdCurrencyAdapter(decimal_places=4))
```

### 实例注册

```python
# 为特定后端实例注册
backend = FirebirdBackend(config=config)
backend.register_adapter(CustomEmailAdapter())
```

## 适配器示例

### 电话号码适配器

```python
class PhoneNumberAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {str: [str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        # 移除非数字字符
        digits = ''.join(filter(str.isdigit, value))
        return f"+{digits}"
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        # 移除格式
        return ''.join(filter(str.isdigit, value))
```

### JSON 适配器

```python
import json

class JSONAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {dict: [dict, list]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        return json.dumps(value)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value
```

### UUID 适配器

```python
from uuid import UUID

class UUIDAdapter(SQLTypeAdapter):
    @property
    def supported_types(self):
        return {UUID: [UUID, str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, str):
            value = UUID(value)
        return str(value)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        return UUID(value)
```

### 枚举适配器

```python
import enum

class EnumAdapter(SQLTypeAdapter):
    def __init__(self, enum_class):
        self.enum_class = enum_class
    
    @property
    def supported_types(self):
        return {self.enum_class: [self.enum_class, str, int]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return value
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value
        return self.enum_class(value)
```

## 使用自定义适配器

### 自动转换

```python
# 自动使用自定义适配器
backend.execute("INSERT INTO users (email) VALUES (?)", ("TEST@EXAMPLE.COM",))
result = backend.execute("SELECT email FROM users WHERE id = 1")
# result[0][0] 是 "test@example.com"
```

### 与模型一起使用

```python
from rhosocial.activerecord.model import ActiveRecord

class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    email: str  # 自动使用 CustomEmailAdapter

# 创建用户
user = User(email="TEST@EXAMPLE.COM")
user.save()
# 电子邮件存储为 "test@example.com"
```

## 最佳实践

### 保持适配器简单

```python
# 好：简单、专注的适配器
class EmailAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return value.lower() if value else None

# 避免：过于复杂的适配器
class ComplexAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        # 逻辑太多
```

### 处理 None 值

```python
# 好：始终处理 None
class SafeAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        return value.lower()

# 避免：不处理 None
class UnsafeAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return value.lower()  # 如果 value 为 None 将失败
```

### 验证输入

```python
# 好：验证输入
class ValidatingAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(f"无效的电子邮件: {value}")
        return value.lower()

# 避免：不验证
class UnvalidatingAdapter(SQLTypeAdapter):
    def to_database(self, value, target_type, options=None):
        return value.lower()  # 无验证
```

💡 *AI 提示:* "如何为 Firebird 特定数据类型创建自定义适配器？"