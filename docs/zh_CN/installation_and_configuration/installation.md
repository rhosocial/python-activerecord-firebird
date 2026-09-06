# 安装指南

## 先决条件

- Python 3.11 或更高版本
- Firebird 数据库服务器（建议 3.0+）
- `firebird-driver` Python 包

## 安装

### 基本安装

```bash
pip install rhosocial-activerecord-firebird
```

### 带可选依赖项

```bash
# 支持连接池
pip install rhosocial-activerecord-firebird[pooling]

# 用于开发
pip install rhosocial-activerecord-firebird[dev,test]
```

## 驱动程序设置

### firebird-driver

后端使用 `firebird-driver` 进行数据库连接。这将作为依赖项自动安装。

### 客户端库

需要 Firebird 客户端库。在 Linux 上：

```bash
# Ubuntu/Debian
sudo apt-get install firebird3.0-client

# CentOS/RHEL
sudo yum install firebird-client
```

在 Windows 上，客户端库包含在 Firebird 安装中。

## 环境变量

### 客户端库路径

如果客户端库不在标准路径中：

```bash
export FIREBIRD_CLIENT_LIBRARY=/path/to/libfbclient.so
```

### 数据库配置

```bash
export FIREBIRD_HOST=localhost
export FIREBIRD_PORT=3050
export FIREBIRD_DATABASE=/data/myapp.fdb
export FIREBIRD_USERNAME=SYSDBA
export FIREBIRD_PASSWORD=masterkey
```

## 验证

### 测试安装

```python
from rhosocial.activerecord.backend.impl.firebird import FirebirdBackend
from rhosocial.activerecord.backend.impl.firebird.config import FirebirdConnectionConfig

config = FirebirdConnectionConfig(
    host="localhost",
    database="/tmp/test.fdb",
    username="SYSDBA",
    password="masterkey"
)

backend = FirebirdBackend(config=config)
backend.connect()
print("安装成功！")
backend.disconnect()
```

### 检查版本

```python
import firebird.driver
print(f"firebird-driver 版本: {firebird.driver.__version__}")
```

💡 *AI 提示:* "如何在不同操作系统上安装 Firebird？"