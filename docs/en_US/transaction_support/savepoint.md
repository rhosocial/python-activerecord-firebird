# Savepoint

## Overview

Firebird supports savepoints for nested transactions and conditional rollback within a transaction.

## Basic Usage

### Creating Savepoints

```python
# Create savepoint
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # Create savepoint
    backend.transaction.savepoint("after_insert")
    
    backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
    
    # Rollback to savepoint if needed
    backend.transaction.rollback_savepoint("after_insert")
    
    # Only Alice remains, order is rolled back
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### Release Savepoint

```python
# Release savepoint (cannot rollback after release)
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # Create and release savepoint
    backend.transaction.savepoint("step1")
    backend.execute("INSERT INTO orders (user_id) VALUES (?)", (1,))
    backend.transaction.release_savepoint("step1")
    
    # Cannot rollback to step1 anymore
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## Nested Transactions

### Simulating Nested Transactions

```python
# Simulate nested transactions
backend.transaction.begin()
try:
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    
    # Create savepoint for nested operation
    backend.transaction.savepoint("nested")
    try:
        backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
        backend.transaction.release_savepoint("nested")
    except:
        backend.transaction.rollback_savepoint("nested")
        # Continue with outer transaction
    
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

### Multiple Levels

```python
# Multiple nested levels
backend.transaction.begin()
try:
    # Level 1
    backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
    backend.transaction.savepoint("level1")
    
    # Level 2
    backend.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", (1, 100))
    backend.transaction.savepoint("level2")
    
    # Level 3
    backend.execute("INSERT INTO order_items (order_id, product_id) VALUES (?, ?)", (1, 1))
    backend.transaction.savepoint("level3")
    
    # Rollback to level2
    backend.transaction.rollback_savepoint("level2")
    # Level 3 changes are lost, but level 1 and 2 remain
    
    backend.transaction.commit()
except:
    backend.transaction.rollback()
```

## Conditional Rollback

### Error Handling with Savepoints

```python
def process_order(backend, user_id, order_data):
    backend.transaction.begin()
    try:
        # Create order
        backend.execute("INSERT INTO orders (user_id, total) VALUES (?, ?)", 
                       (user_id, order_data['total']))
        backend.transaction.savepoint("order_created")
        
        try:
            # Process payment
            process_payment(backend, order_data)
            backend.transaction.release_savepoint("order_created")
        except PaymentError:
            # Payment failed, rollback order
            backend.transaction.rollback_savepoint("order_created")
            raise
        
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise
```

### Batch Processing with Savepoints

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
                # Rollback this item, continue with others
                backend.transaction.rollback_savepoint(f"batch_{i}")
                print(f"Failed to insert item {i}: {e}")
        
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise
```

## Best Practices

### Use Meaningful Names

```python
# Good: Descriptive savepoint names
backend.transaction.savepoint("before_payment")
backend.transaction.savepoint("after_validation")

# Avoid: Cryptic names
backend.transaction.savepoint("sp1")
backend.transaction.savepoint("sp2")
```

### Keep Transactions Short

```python
# Good: Short transaction with savepoint
backend.transaction.begin()
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
backend.transaction.savepoint("user_created")
backend.execute("INSERT INTO orders (user_id) VALUES (?)", (1,))
backend.transaction.commit()

# Bad: Long transaction with many savepoints
backend.transaction.begin()
# Many operations...
backend.transaction.commit()
```

### Clean Up Savepoints

```python
# Release savepoints when no longer needed
backend.transaction.begin()
backend.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
backend.transaction.savepoint("step1")
backend.execute("INSERT INTO orders (user_id) VALUES (?)", (1,))
backend.transaction.release_savepoint("step1")
backend.transaction.commit()
```

## Error Handling

### Savepoint Errors

```python
try:
    backend.transaction.savepoint("invalid savepoint")
except Exception as e:
    print(f"Savepoint error: {e}")
```

### Recovery from Savepoint Failure

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
            # Continue with valid data
        
        backend.transaction.commit()
    except:
        backend.transaction.rollback()
        raise
```

💡 *AI Prompt:* "When should I use savepoints vs separate transactions?"