# 保存点

## 概述

Firebird 支持保存点，用于事务内的嵌套事务和条件回滚。

## 基本用法

### 创建保存点

```python
# 创建保存点
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # 创建保存点
    backend.transaction.savepoint("after_insert")
    
    backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
    
    # 如果需要，回滚到保存点
    backend.transaction.rollback_savepoint("after_insert")
    
    # 只有 Alice 保留，订单被回滚
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### 释放保存点

```python
# 释放保存点（释放后无法回滚）
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # 创建并释放保存点
    backend.transaction.savepoint("step1")
    backend.execute("INSERT INTO orders (user_id) VALUES (?)", (1,))
    backend.transaction.release_savepoint("step1")
    
    # 无法再回滚到 step1
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## 嵌套事务

### 模拟嵌套事务

```python
# 模拟嵌套事务
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # 为嵌套操作创建保存点
    backend.transaction.savepoint("nested")
    try:
        backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
        backend.transaction.release_savepoint("nested")
    except:
        backend.transaction.rollback_savepoint("nested")
        # 继续外部事务
    
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### 多层嵌套

```python
# 多层嵌套
backend.transaction.begin()
try:
    # 第 1 层
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    backend.transaction.savepoint("level1")
    
    # 第 2 层
    backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
    backend.transaction.savepoint("level2")
    
    # 第 3 层
    backend.execute("INSERT INTO order_items (order_id, product_id) VALUES (?, ?)", (1, 1))
    backend.transaction.savepoint("level3")
    
    # 回滚到第 2 层
    backend.transaction.rollback_savepoint("level2")
    # 第 3 层更改丢失，但第 1 层和第 2 层保留
    
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## 条件回滚

### 使用保存点的错误处理

```python
def process_order(backend, user_id, order_data):
    backend.transaction.begin()
    try:
        # 创建订单
        backend.execute("INSERT INTO orders (user_id, total) VALUES (?, ?)", 
                       (user_id, order_data['total']))
        backend.transaction.savepoint("order_created")
        
        try:
            # 处理支付
            process_payment(backend, order_data)
            backend.transaction.release_savepoint("order_created")
        except PaymentError:
            # 支付失败，回滚订单
            backend.transaction.rollback_savepoint("order_created")
            raise
        
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise
```

### 批量处理与保存点

```python
def batch_insert(backend, data_list):
    backend.transaction.begin()
    try:
        for i, data in enumerate(data_list):
            try:
                backend.execute("INSERT INTO large_table (col1, col2) VALUES (?, ?)",
                               (data['col1'], data['col2']))
                backend.transaction.savepoint(f"batch_{i}")
            except Exception as e:
                # 回滚此项，继续其他项
                backend.transaction.rollback_savepoint(f"batch_{i}")
                print(f"插入项目 {i} 失败: {e}")
        
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise
```

## 最佳实践

### 使用有意义的名称

```python
# 好：描述性保存点名称
backend.transaction.savepoint("before_payment")
backend.transaction.savepoint("after_validation")

# 避免：神秘的名称
backend.transaction.savepoint("sp1")
backend.transaction.savepoint("sp2")
```

### 保持事务简短

```python
# 好：带保存点的简短事务
backend.transaction.begin()
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
backend.transaction.savepoint("user_created")
backend.execute("INSERT INTO orders (user_id) VALUES (?)", (1,))
backend.transaction.commit()

# 不好：带多个保存点的长事务
backend.transaction.begin()
# 许多操作...
backend.transaction.commit()
```

### 清理保存点

```python
# 不再需要时释放保存点
backend.transaction.begin()
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
backend.transaction.savepoint("step1")
backend.execute("INSERT INTO orders (user_id) VALUES (?)", (1,))
backend.transaction.release_savepoint("step1")
backend.transaction.commit()
```

## 错误处理

### 保存点错误

```python
try:
    backend.transaction.savepoint("invalid savepoint")
except Exception as e:
    print(f"保存点错误: {e}")
```

### 从保存点失败中恢复

```python
def safe_operation(backend):
    backend.transaction.begin()
    try:
        backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
        backend.transaction.savepoint("user_created")
        
        try:
            backend.execute("INSERT INTO invalid_table (col) VALUES (?)", ("value",))
        except:
            backend.transaction.rollback_savepoint("user_created")
            # 继续有效数据
        
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise
```

💡 *AI 提示:* "何时应使用保存点而不是单独的事务？"