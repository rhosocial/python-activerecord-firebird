# 自定义表达式

## 概述

自定义表达式允许您为复杂操作定义 Firebird 特定的 SQL 语法。

## 创建自定义表达式

### 基本表达式

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
print(expr.to_sql(None))
```

### 带参数的表达式

```python
class ParameterizedExpression(Expression):
    """带输入参数的表达式。"""
    
    def __init__(self, params, declarations=None, statements=None):
        self.params = params
        self.declarations = declarations or []
        self.statements = statements or []
    
    def to_sql(self, dialect):
        sql = "EXECUTE BLOCK"
        
        if self.params:
            param_str = ", ".join(f"{k} {v} = ?" for k, v in self.params.items())
            sql += f" ({param_str})"
        
        if self.declarations:
            declarations_sql = "; ".join(self.declarations)
            sql += f" AS\nDECLARE {declarations_sql}"
        
        if self.statements:
            statements_sql = "\n    ".join(self.statements)
            sql += f"\nBEGIN\n    {statements_sql}\nEND"
        
        return sql

# 使用
expr = ParameterizedExpression(
    params={"user_id": "INTEGER", "action": "VARCHAR(50)"},
    declarations=["user_name VARCHAR(100)"],
    statements=[
        "SELECT name INTO user_name FROM users WHERE id = :user_id",
        "INSERT INTO audit_log (user_id, user_name, action) VALUES (:user_id, :user_name, :action)"
    ]
)
```

## 注册表达式

### 全局注册

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# 全局注册表达式
FirebirdBackend.register_expression("execute_block", ExecuteBlockExpression)
```

### 方言集成

```python
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

class CustomFirebirdDialect(FirebirdDialect):
    """具有新表达式的自定义方言。"""
    
    def execute_block(self, declarations=None, statements=None):
        """创建 EXECUTE BLOCK 表达式。"""
        return ExecuteBlockExpression(declarations, statements)
    
    def parameterized_block(self, params, declarations=None, statements=None):
        """创建参数化 EXECUTE BLOCK。"""
        return ParameterizedExpression(params, declarations, statements)
```

## 表达式示例

### MERGE 表达式

```python
class MergeExpression(Expression):
    """用于 MERGE 语句的自定义表达式。"""
    
    def __init__(self, target, source, match_condition, matched_action, not_matched_action):
        self.target = target
        self.source = source
        self.match_condition = match_condition
        self.matched_action = matched_action
        self.not_matched_action = not_matched_action
    
    def to_sql(self, dialect):
        sql = f"""
MERGE INTO {self.target} t
USING {self.source} s ON {self.match_condition}
WHEN MATCHED THEN
    {self.matched_action}
WHEN NOT MATCHED THEN
    {self.not_matched_action}
"""
        return sql.strip()

# 使用
expr = MergeExpression(
    target="target_table",
    source="source_table",
    match_condition="t.id = s.id",
    matched_action="UPDATE SET t.name = s.name",
    not_matched_action="INSERT (id, name) VALUES (s.id, s.name)"
)
```

### 递归 CTE 表达式

```python
class RecursiveCTEExpression(Expression):
    """用于递归 CTE 的自定义表达式。"""
    
    def __init__(self, name, base_query, recursive_query, final_query):
        self.name = name
        self.base_query = base_query
        self.recursive_query = recursive_query
        self.final_query = final_query
    
    def to_sql(self, dialect):
        sql = f"""
WITH RECURSIVE {self.name} AS (
    {self.base_query}
    UNION ALL
    {self.recursive_query}
)
{self.final_query}
"""
        return sql.strip()

# 使用
expr = RecursiveCTEExpression(
    name="org_chart",
    base_query="SELECT id, name, manager_id, 1 as level FROM employees WHERE manager_id IS NULL",
    recursive_query="SELECT e.id, e.name, e.manager_id, oc.level + 1 FROM employees e JOIN org_chart oc ON e.manager_id = oc.id",
    final_query="SELECT * FROM org_chart"
)
```

## 在查询中使用

### 使用表达式

```python
# 创建表达式
expr = ExecuteBlockExpression(
    declarations=["total INTEGER"],
    statements=[
        "SELECT COUNT(*) INTO total FROM users",
        "INSERT INTO stats (count_value) VALUES (total)"
    ]
)

# 执行表达式
backend.execute(expr.to_sql(None))
```

### 带参数

```python
# 创建参数化表达式
expr = ParameterizedExpression(
    params={"user_id": "INTEGER"},
    declarations=["user_name VARCHAR(100)"],
    statements=[
        "SELECT name INTO user_name FROM users WHERE id = :user_id",
        "INSERT INTO audit_log (user_name) VALUES (:user_name)"
    ]
)

# 带参数执行
backend.execute(expr.to_sql(None), (1,))
```

## 最佳实践

### 保持表达式简单

```python
# 好：简单、专注的表达式
class SimpleExpression(Expression):
    def to_sql(self, dialect):
        return "EXECUTE BEGIN INSERT INTO log VALUES (1); END"

# 避免：过于复杂的表达式
class ComplexExpression(Expression):
    def to_sql(self, dialect):
        # 逻辑太多
```

### 使用有意义的名称

```python
# 好：描述性类名
class ExecuteBlockExpression(Expression):
    pass

class MergeExpression(Expression):
    pass

# 避免：神秘的名称
class Expr1(Expression):
    pass
```

### 验证输入

```python
# 好：验证输入
class SafeExpression(Expression):
    def __init__(self, statements):
        if not statements:
            raise ValueError("语句不能为空")
        self.statements = statements

# 避免：不验证
class UnsafeExpression(Expression):
    def __init__(self, statements):
        self.statements = statements  # 无验证
```

💡 *AI 提示:* "如何为 Firebird 的 EXECUTE BLOCK 创建自定义表达式？"