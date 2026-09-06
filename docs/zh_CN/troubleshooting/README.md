# 故障排除

## 连接错误

### 常见连接问题

#### 错误：连接被拒绝

```
Error: Connection refused
```

**原因：**
- Firebird 服务器未运行
- 主机或端口错误
- 防火墙阻止连接

**解决方案：**

```bash
# 检查 Firebird 是否运行
sudo systemctl status firebird3.0

# 使用 isql 测试连接
isql-fb -user SYSDBA -password masterkey -host localhost -port 3050

# 检查防火墙
sudo ufw status
sudo ufw allow 3050/tcp
```

#### 错误：无法完成网络请求

```
Error: Unable to complete network request to host "localhost"
```

**原因：**
- 端口号错误
- 网络配置问题
- Firebird 未监听网络接口

**解决方案：**

```python
# 验证配置
config = FirebirdConnectionConfig(
    host="localhost",  # 或 IP 地址
    port=3050,         # 默认 Firebird 端口
    database="/data/myapp.fdb"
)

# 检查 Firebird 配置
# 编辑 /etc/firebird/3.0/firebird.conf
# 确保 RemoteServiceName = gds_db (端口 3050)
```

#### 错误：无法附加到数据库

```
Error: Cannot attach to database file "/data/myapp.fdb"
```

**原因：**
- 数据库文件不存在
- 权限错误
- 数据库路径不正确

**解决方案：**

```bash
# 检查数据库文件是否存在
ls -la /data/myapp.fdb

# 检查权限
sudo chown firebird:firebird /data/myapp.fdb
sudo chmod 660 /data/myapp.fdb

# 如果需要，创建数据库
isql-fb -user SYSDBA -password masterkey
> CREATE DATABASE '/data/myapp.fdb';
> EXIT;
```

#### 错误：登录不匹配

```
Error: login mismatch
```

**原因：**
- 用户名或密码错误
- 用户不存在
- 认证方法不匹配

**解决方案：**

```bash
# 重置 SYSDBA 密码
isql-fb -user SYSDBA -password masterkey
> ALTER USER SYSDBA SET PASSWORD 'new_password';
> EXIT;

# 创建新用户
isql-fb -user SYSDBA -password masterkey
> CREATE USER app_user PASSWORD 'app_password';
> EXIT;
```

### 自动恢复

后端包含针对瞬态错误的自动重连：

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)

backend = FirebirdBackend(config=config)

# 连接丢失时后端将尝试自动重连
try:
    backend.connect()
    # 使用后端
except Exception as e:
    # 处理永久性故障
    print(f"连接失败: {e}")
```

## 性能问题

### 慢查询分析

#### 启用查询日志

```python
import logging

# 启用查询日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('rhosocial.activerecord')
logger.setLevel(logging.DEBUG)
```

#### 使用 EXPLAIN

```python
# 分析查询执行计划
result = backend.execute("""
    EXPLAIN SELECT * FROM users 
    WHERE email LIKE '%@example.com' 
    ORDER BY created_at DESC
""")
print(result)
```

### 常见性能问题

#### 缺少索引

```python
# 检查缺少的索引
result = backend.execute("""
    SELECT rdb$relation_name, rdb$field_name
    FROM rdb$relation_fields
    WHERE rdb$relation_name = 'USERS'
    ORDER BY rdb$field_position
""")

# 创建适当的索引
backend.execute("CREATE INDEX idx_users_email ON users (email)")
backend.execute("CREATE INDEX idx_users_created_at ON users (created_at)")
```

#### 大结果集

```python
# 对大结果集使用分页
def get_users_page(backend, page=1, per_page=100):
    offset = (page - 1) * per_page
    return backend.execute("""
        SELECT * FROM users 
        ORDER BY id 
        ROWS ? TO ?
    """, (offset + 1, offset + per_page))
```

#### 连接池耗尽

```python
# 监控连接池
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=10,  # 增加池大小
    pool_timeout=60  # 增加超时时间
)
```

### 锁冲突

#### 检测锁冲突

```python
from rhosocial.activerecord.backend import errors as exc

try:
    backend.transaction.begin()
    # 长时间运行的操作
    backend.transaction.commit()
except exc.LockConflictError as e:
    print(f"检测到锁冲突: {e}")
    backend.transaction.rollback()
```

#### 减少锁冲突

```python
# 使用更短的事务
backend.transaction.begin()
try:
    # 仅快速操作
    backend.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (100, 1))
    backend.transaction.commit()
except:
    backend.transaction.rollback()

# 需要时使用显式锁定
backend.execute("""
    SELECT * FROM accounts 
    WHERE id = 1 
    WITH LOCK
""")
```

## SQL 标准兼容性

### Firebird SQL 方言

Firebird 默认使用 SQL 方言 3。某些 SQL 标准功能有所不同：

```python
# Firebird 使用双引号表示标识符
backend.execute('SELECT * FROM "users" WHERE "email" = ?', ('test@example.com',))

# 字符串连接使用 ||
backend.execute("SELECT first_name || ' ' || last_name AS full_name FROM users")

# 布尔值使用 1/0 或 TRUE/FALSE (Firebird 3.0+)
backend.execute("SELECT * FROM users WHERE active = TRUE")
```

### 日期/时间函数

```python
# Firebird 日期函数
backend.execute("SELECT CURRENT_DATE FROM rdb$database")
backend.execute("SELECT CURRENT_TIMESTAMP FROM rdb$database")
backend.execute("SELECT CAST('2026-01-01' AS DATE) FROM rdb$database")
```

## 错误代码

### 常见 Firebird 错误代码

| 错误代码 | 描述 | 解决方案 |
|----------|------|----------|
| 335544336 | 锁冲突 | 重试事务或使用更短的事务 |
| 335544349 | 外键违规 | 检查引用表 |
| 335544350 | 主键违规 | 检查重复键 |
| 335544558 | 连接被拒绝 | 检查 Firebird 服务器状态 |
| 335544569 | 无法附加到数据库 | 检查数据库路径和权限 |

### 错误处理

```python
from rhosocial.activerecord.backend import errors as exc

try:
    backend.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
except exc.IntegrityError as e:
    print(f"完整性错误: {e}")
except exc.DatabaseError as e:
    print(f"数据库错误: {e}")
except exc.ConnectionError as e:
    print(f"连接错误: {e}")
```

💡 *AI 提示:* "如何排除 Firebird 连接超时问题？"