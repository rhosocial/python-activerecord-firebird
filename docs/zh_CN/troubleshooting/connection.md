# 连接错误

## 概述

本节介绍常见连接错误及其解决方案。

## 常见连接问题

### 错误：连接被拒绝

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

### 错误：无法完成网络请求

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

### 错误：无法附加到数据库

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

### 错误：登录不匹配

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

## 自动恢复

### 连接重试

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

### 连接验证

```python
# 使用前测试连接
if backend.is_connected:
    result = backend.execute("SELECT 1 FROM rdb$database")
else:
    backend.connect()
    result = backend.execute("SELECT 1 FROM rdb$database")
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

## 故障排除步骤

### 1. 检查服务器状态

```bash
# 检查 Firebird 是否运行
sudo systemctl status firebird3.0

# 检查端口
netstat -tlnp | grep 3050
```

### 2. 验证配置

```python
# 打印配置
print(config.to_dict())
```

### 3. 测试连接

```python
# 简单连接测试
try:
    backend.connect()
    print("连接成功！")
except Exception as e:
    print(f"连接失败: {e}")
finally:
    backend.disconnect()
```

### 4. 检查日志

```bash
# 检查 Firebird 日志
tail -f /var/log/firebird3.0/*.log
```

## 预防

### 使用连接池

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    pool_size=5,
    pool_timeout=30
)
```

### 设置超时

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    timeout=30
)
```

### 优雅地处理错误

```python
try:
    backend.execute("SELECT * FROM users")
except exc.ConnectionError:
    backend.connect()
    backend.execute("SELECT * FROM users")
```

💡 *AI 提示:* "如何排除 Firebird 连接超时问题？"