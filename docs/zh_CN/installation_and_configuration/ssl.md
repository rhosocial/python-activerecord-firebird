# SSL/TLS 配置

## 概述

Firebird 支持 SSL/TLS 加密连接，用于安全通信。

## 配置

### 基本 SSL 设置

```python
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    ssl=True
)
```

### SSL 证书选项

| 选项 | 描述 |
|------|------|
| `ssl` | 启用 SSL/TLS |
| `ssl_ca` | CA 证书文件 |
| `ssl_cert` | 客户端证书文件 |
| `ssl_key` | 客户端密钥文件 |

### 完整 SSL 配置

```python
config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    ssl=True,
    ssl_ca="/path/to/ca.pem",
    ssl_cert="/path/to/client-cert.pem",
    ssl_key="/path/to/client-key.pem"
)
```

## 生成证书

### 自签名证书

```bash
# 生成 CA 密钥和证书
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -out ca.pem

# 生成服务器密钥和证书
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -days 365 -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out server.pem

# 生成客户端密钥和证书
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr
openssl x509 -req -days 365 -in client.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out client.pem
```

## Firebird 服务器配置

### 在 Firebird 中启用 SSL

编辑 `firebird.conf`：

```
WireCrypt = SSL
```

### 重启 Firebird

```bash
sudo systemctl restart firebird3.0
```

## 测试 SSL 连接

### 使用 Python 测试

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/data/myapp.fdb",
    username="SYSDBA",
    password="masterkey",
    ssl=True,
    ssl_ca="/path/to/ca.pem"
)

backend = FirebirdBackend(config=config)
backend.connect()
print("SSL 连接成功！")
backend.disconnect()
```

### 使用 isql 测试

```bash
isql-fb -user SYSDBA -password masterkey -host localhost -port 3050 -database /data/myapp.fdb
```

## 故障排除

### 常见 SSL 问题

1. **证书验证失败**
   - 检查 CA 证书路径
   - 确保证书未过期

2. **连接被拒绝**
   - 验证 Firebird 服务器已启用 SSL
   - 检查防火墙规则

3. **密钥/证书不匹配**
   - 确保密钥和证书匹配
   - 如需要，重新生成证书

💡 *AI 提示:* "如何为 Firebird 数据库连接设置 SSL/TLS？"