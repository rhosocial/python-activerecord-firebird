# Custom Expressions

## Overview

Custom expressions allow you to define Firebird-specific SQL syntax for complex operations.

## Creating Custom Expressions

### Basic Expression

```python
from rhosocial.activerecord.backend.dialect.base import Expression

class ExecuteBlockExpression(Expression):
    """Custom expression for EXECUTE BLOCK."""
    
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

# Usage
expr = ExecuteBlockExpression(
    declarations=["cnt INTEGER"],
    statements=[
        "SELECT COUNT(*) INTO cnt FROM users",
        "INSERT INTO stats (count_value) VALUES (cnt)"
    ]
)
print(expr.to_sql(None))
```

### Parameterized Expression

```python
class ParameterizedExpression(Expression):
    """Expression with input parameters."""
    
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

# Usage
expr = ParameterizedExpression(
    params={"user_id": "INTEGER", "action": "VARCHAR(50)"},
    declarations=["user_name VARCHAR(100)"],
    statements=[
        "SELECT name INTO user_name FROM users WHERE id = :user_id",
        "INSERT INTO audit_log (user_id, user_name, action) VALUES (:user_id, :user_name, :action)"
    ]
)
```

## Registering Expressions

### Global Registration

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend

# Register expression globally
FirebirdBackend.register_expression("execute_block", ExecuteBlockExpression)
```

### Dialect Integration

```python
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

class CustomFirebirdDialect(FirebirdDialect):
    """Custom dialect with new expressions."""
    
    def execute_block(self, declarations=None, statements=None):
        """Create EXECUTE BLOCK expression."""
        return ExecuteBlockExpression(declarations, statements)
    
    def parameterized_block(self, params, declarations=None, statements=None):
        """Create parameterized EXECUTE BLOCK."""
        return ParameterizedExpression(params, declarations, statements)
```

## Expression Examples

### MERGE Expression

```python
class MergeExpression(Expression):
    """Custom expression for MERGE statement."""
    
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

# Usage
expr = MergeExpression(
    target="target_table",
    source="source_table",
    match_condition="t.id = s.id",
    matched_action="UPDATE SET t.name = s.name",
    not_matched_action="INSERT (id, name) VALUES (s.id, s.name)"
)
```

### Recursive CTE Expression

```python
class RecursiveCTEExpression(Expression):
    """Custom expression for recursive CTE."""
    
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

# Usage
expr = RecursiveCTEExpression(
    name="org_chart",
    base_query="SELECT id, name, manager_id, 1 as level FROM employees WHERE manager_id IS NULL",
    recursive_query="SELECT e.id, e.name, e.manager_id, oc.level + 1 FROM employees e JOIN org_chart oc ON e.manager_id = oc.id",
    final_query="SELECT * FROM org_chart"
)
```

## Usage in Queries

### Using Expressions

```python
# Create expression
expr = ExecuteBlockExpression(
    declarations=["total INTEGER"],
    statements=[
        "SELECT COUNT(*) INTO total FROM users",
        "INSERT INTO stats (count_value) VALUES (total)"
    ]
)

# Execute expression
backend.execute(expr.to_sql(None))
```

### With Parameters

```python
# Create parameterized expression
expr = ParameterizedExpression(
    params={"user_id": "INTEGER"},
    declarations=["user_name VARCHAR(100)"],
    statements=[
        "SELECT name INTO user_name FROM users WHERE id = :user_id",
        "INSERT INTO audit_log (user_name) VALUES (:user_name)"
    ]
)

# Execute with parameters
backend.execute(expr.to_sql(None), (1,))
```

## Best Practices

### Keep Expressions Simple

```python
# Good: Simple, focused expression
class SimpleExpression(Expression):
    def to_sql(self, dialect):
        return "EXECUTE BEGIN INSERT INTO log VALUES (1); END"

# Avoid: Overly complex expression
class ComplexExpression(Expression):
    def to_sql(self, dialect):
        # Too much logic
```

### Use Meaningful Names

```python
# Good: Descriptive class names
class ExecuteBlockExpression(Expression):
    pass

class MergeExpression(Expression):
    pass

# Avoid: Cryptic names
class Expr1(Expression):
    pass
```

### Validate Input

```python
# Good: Validate input
class SafeExpression(Expression):
    def __init__(self, statements):
        if not statements:
            raise ValueError("Statements cannot be empty")
        self.statements = statements

# Avoid: No validation
class UnsafeExpression(Expression):
    def __init__(self, statements):
        self.statements = statements  # No validation
```

💡 *AI Prompt:* "How do I create a custom expression for Firebird's EXECUTE BLOCK?"