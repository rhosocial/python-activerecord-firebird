# 自定义

## 概述

Firebird 后端支持通过自定义表达式、数据类型和类型适配器进行广泛自定义。本节介绍如何扩展后端以满足特定用例需求。

## 自定义表达式

### 创建自定义表达式类

自定义表达式允许您定义 Firebird 特定的 SQL 语法：

```python
from rhosocial.activerecord.backend.dialect.base import Expression

class ExecuteBlockExpression(Expression):
    """用于 EXECUTE BLOCK 的自定义表达式。"""
    
    def __init__(self, declarations=None, statements=None):
        self.declarations = declarations or []
        self.statements = statements or []
    
    def to_sql(self, dialect):
        sql = "EXECUTE BLOCK"
        
        if self.declarations:
            declarations_sql = "; ".join(self.declarations)
            sql += f" AS\nDECLARE {declarations_sql}"
        
        if self.statements:
            statements_sql = "\n    ".join(self.statements)
            sql += f"\nBEGIN\n    {statements_sql}\nEND"
        
        return sql

# 使用
expr = ExecuteBlockExpression(
    declarations=["cnt INTEGER"],
    statements=[
        "SELECT COUNT(*) INTO cnt FROM users",
        "INSERT INTO stats (count_value) VALUES (cnt)"
    ]
)
```

### 注册自定义表达式

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# 全局注册表达式
FirebirdBackend.register_expression("execute_block", ExecuteBlockExpression)

# 或在方言中使用
class CustomFirebirdDialect(FirebirdDialect):
    def execute_block(self, declarations=None, statements=None):
        return ExecuteBlockExpression(declarations, statements)
```

## 自定义数据类型

### 定义新的 DataType 子类

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

### 自定义域类型

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

## 自定义类型适配器

### 注册自定义转换器

```python
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

class FirebirdPhoneNumberAdapter(SQLTypeAdapter):
    """电话号码的自定义适配器。"""
    
    @property
    def supported_types(self):
        return {str: [str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        # 移除非数字字符
        digits = ''.join(filter(str.isdigit, value))
        # 格式化为 Firebird 友好字符串
        return f"+{digits}"
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        # 移除格式
        return ''.join(filter(str.isdigit, value))

# 注册适配器
FirebirdBackend.register_adapter(FirebirdPhoneNumberAdapter())
```

### 带选项的类型适配器

```python
class FirebirdCurrencyAdapter(SQLTypeAdapter):
    """带小数位选项的货币适配器。"""
    
    def __init__(self, decimal_places=2):
        self.decimal_places = decimal_places
    
    @property
    def supported_types(self):
        return {Decimal: [Decimal, float, int, str]}
    
    def to_database(self, value, target_type, options=None):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        return round(value, self.decimal_places)
    
    def from_database(self, value, target_type, options=None):
        if value is None:
            return None
        return Decimal(str(value))

# 使用带选项的适配器
adapter = FirebirdCurrencyAdapter(decimal_places=4)
FirebirdBackend.register_adapter(adapter)
```

## 方言自定义

### 扩展 Firebird 方言

```python
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

class CustomFirebirdDialect(FirebirdDialect):
    """具有附加功能的自定义 Firebird 方言。"""
    
    def custom_function(self, *args):
        """添加自定义函数支持。"""
        return f"CUSTOM_FUNC({', '.join(str(a) for a in args)})"
    
    def upsert(self, table, data, conflict_columns):
        """使用 MERGE 的自定义 UPSERT 实现。"""
        merge_sql = f"""
            MERGE INTO {table} t
            USING (SELECT ? AS id, ? AS name) s
            ON t.id = s.id
            WHEN MATCHED THEN
                UPDATE SET t.name = s.name
            WHEN NOT MATCHED THEN
                INSERT (id, name) VALUES (s.id, s.name)
        """
        return merge_sql

# 注册自定义方言
FirebirdBackend.dialect_class = CustomFirebirdDialect
```

## 模型自定义

### 自定义模型基类

```python
from rhosocial.activerecord.model import ActiveRecord

class FirebirdModel(ActiveRecord):
    """Firebird 的自定义模型基类。"""
    
    __abstract__ = True
    
    @classmethod
    def find_by_email(cls, email):
        """按电子邮件查找用户（不区分大小写）。"""
        return cls.query().where(
            "LOWER(email) = LOWER(?)", (email,)
        ).one()
    
    def soft_delete(self):
        """带时间戳的软删除。"""
        self.deleted_at = datetime.now()
        self.save()
    
    @classmethod
    def active(cls):
        """仅获取活动（未删除）记录。"""
        from rhosocial.activerecord.backend.expression import Column
        expr = Column(dialect, "deleted_at").is_null()
        return cls.query().where(expr)
```

### 自定义查询构建器

```python
class FirebirdQuery:
    """具有 Firebird 特定功能的自定义查询构建器。"""
    
    def __init__(self, backend, model):
        self.backend = backend
        self.model = model
    
    def with_row_number(self, partition_by=None, order_by=None):
        """添加 ROW_NUMBER() 窗口函数。"""
        sql = f"SELECT *, ROW_NUMBER() OVER ("
        if partition_by:
            sql += f"PARTITION BY {partition_by} "
        if order_by:
            sql += f"ORDER BY {order_by}"
        sql += f") as row_num FROM {self.model.__table_name__}"
        return self.backend.execute(sql)
    
    def execute_block(self, declarations, statements):
        """执行 EXECUTE BLOCK。"""
        expr = ExecuteBlockExpression(declarations, statements)
        return self.backend.execute(expr.to_sql(None))
```

## 配置自定义

### 自定义配置 Mixin

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class FirebirdExtendedConfig(FirebirdConnectionConfig):
    """具有附加选项的扩展配置。"""
    
    # 连接选项
    connection_timeout: int = 30
    query_timeout: int = 60
    
    # 日志选项
    log_queries: bool = False
    log_slow_queries: bool = True
    slow_query_threshold: float = 1.0  # 秒
    
    # 性能选项
    fetch_size: int = 100
    array_size: int = 100

# 使用
config = FirebirdExtendedConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    log_queries=True,
    slow_query_threshold=0.5
)
```

## 插件系统

### 创建插件

```python
class FirebirdPlugin:
    """Firebird 插件的基类。"""
    
    def __init__(self, backend):
        self.backend = backend
    
    def on_connect(self):
        """连接建立时调用。"""
        pass
    
    def on_disconnect(self):
        """连接关闭时调用。"""
        pass
    
    def on_query(self, query, params):
        """查询执行前调用。"""
        pass

class LoggingPlugin(FirebirdPlugin):
    """用于查询日志的插件。"""
    
    def on_query(self, query, params):
        print(f"执行: {query}")
        print(f"参数: {params}")

# 注册插件
backend = FirebirdBackend(config=config)
backend.register_plugin(LoggingPlugin(backend))
```

💡 *AI 提示:* "如何为 Firebird 的 EXECUTE BLOCK 创建自定义表达式？"