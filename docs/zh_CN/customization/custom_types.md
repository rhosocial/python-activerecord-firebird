# 自定义数据类型

## 概述

自定义数据类型允许您定义新的 DataType 子类，用于自定义列类型。

## 创建自定义数据类型

### 基本数据类型

```python
from rhosocial.activerecord.backend.data_type import DataType

class FirebirdJSONType(DataType):
    """使用 BLOB SUB_TYPE 1 的 Firebird JSON 类型。"""
    
    def __init__(self, charset="UTF8"):
        self.charset = charset
    
    def to_sql(self):
        return f"BLOB SUB_TYPE 1 SEGMENT SIZE 16384 CHARACTER SET {self.charset}"
    
    def to_python(self, value):
        if value is None:
            return None
        import json
        if isinstance(value, bytes):
            value = value.decode(self.charset)
        return json.loads(value)
    
    def to_database(self, value):
        if value is None:
            return None
        import json
        return json.dumps(value).encode(self.charset)

# 在模型中使用
class Document(ActiveRecord):
    __table_name__ = "documents"
    id: int
    metadata: FirebirdJSONType = FirebirdJSONType()
```

### 域类型

```python
class FirebirdEmailDomain(DataType):
    """带验证的电子邮件域类型。"""
    
    def to_sql(self):
        return "VARCHAR(255) NOT NULL CHECK (VALUE LIKE '%@%.%')"
    
    def to_python(self, value):
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(f"无效的电子邮件: {value}")
        return value.lower()
    
    def to_database(self, value):
        if value is None:
            return None
        return value.lower()

# 使用
class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    email: FirebirdEmailDomain
```

### 数组类型

```python
class FirebirdArrayDataType(DataType):
    """Firebird 数组类型。"""
    
    def __init__(self, base_type, dimensions):
        self.base_type = base_type
        self.dimensions = dimensions
    
    def to_sql(self):
        dim_strs = []
        for dim in self.dimensions:
            if isinstance(dim, tuple):
                dim_strs.append(f"{dim[0]}:{dim[1]}")
            else:
                dim_strs.append(str(dim))
        return f"{self.base_type}[{' AND '.join(dim_strs)}]"
    
    def to_python(self, value):
        if value is None:
            return None
        return value
    
    def to_database(self, value):
        if value is None:
            return None
        return value

# 使用
class Product(ActiveRecord):
    __table_name__ = "products"
    id: int
    tags: FirebirdArrayDataType = FirebirdArrayDataType('VARCHAR(50)', [10])
```

## 类型转换

### to_sql 方法

```python
class CustomDataType(DataType):
    def to_sql(self):
        """返回 SQL 类型定义。"""
        return "VARCHAR(255)"
```

### to_python 方法

```python
class CustomDataType(DataType):
    def to_python(self, value):
        """将数据库值转换为 Python 值。"""
        if value is None:
            return None
        return str(value).lower()
```

### to_database 方法

```python
class CustomDataType(DataType):
    def to_database(self, value):
        """将 Python 值转换为数据库值。"""
        if value is None:
            return None
        return str(value).upper()
```

## 使用自定义类型

### 在模型中

```python
from rhosocial.activerecord.model import ActiveRecord

class User(ActiveRecord):
    __table_name__ = "users"
    id: int
    email: FirebirdEmailDomain
    metadata: FirebirdJSONType = FirebirdJSONType()

# 创建用户
user = User(email="TEST@EXAMPLE.COM", metadata={"key": "value"})
user.save()
# 电子邮件存储为 "test@example.com"
# 元数据存储为 JSON 字符串
```

### 在查询中

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.operators import BinaryExpression

# 使用表达式查询自定义类型
expr = BinaryExpression(dialect, "=", Column(dialect, "email"), Literal(dialect, "test@example.com"))
user = User.query().where(expr).one()
sql, params = expr.to_sql()
# sql: "email" = %s
# params: ('test@example.com',)
print(user.email)  # "test@example.com"
print(user.metadata)  # {"key": "value"}
```

## 类型验证

### 验证输入

```python
class ValidatingDataType(DataType):
    def to_database(self, value):
        if value is None:
            return None
        # 存储前验证
        if not isinstance(value, str):
            raise ValueError(f"期望字符串，得到 {type(value)}")
        return value.lower()
```

### 验证输出

```python
class ValidatingDataType(DataType):
    def to_python(self, value):
        if value is None:
            return None
        # 读取时验证
        if not isinstance(value, str):
            raise ValueError(f"期望字符串，得到 {type(value)}")
        return value.lower()
```

## 最佳实践

### 保持类型简单

```python
# 好：简单、专注的类型
class SimpleType(DataType):
    def to_sql(self):
        return "VARCHAR(255)"
    
    def to_python(self, value):
        return value.lower() if value else None

# 避免：过于复杂的类型
class ComplexType(DataType):
    def to_sql(self):
        # 逻辑太多
```

### 处理 None 值

```python
# 好：始终处理 None
class SafeType(DataType):
    def to_python(self, value):
        if value is None:
            return None
        return value.lower()

# 避免：不处理 None
class UnsafeType(DataType):
    def to_python(self, value):
        return value.lower()  # 如果 value 为 None 将失败
```

### 验证输入

```python
# 好：验证输入
class ValidatingType(DataType):
    def to_database(self, value):
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(f"无效的电子邮件: {value}")
        return value.lower()

# 避免：不验证
class UnvalidatingType(DataType):
    def to_database(self, value):
        return value.lower()  # 无验证
```

💡 *AI 提示:* "如何为 Firebird 数组创建自定义数据类型？"