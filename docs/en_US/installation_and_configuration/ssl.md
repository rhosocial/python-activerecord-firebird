# SSL/TLS Configuration

## Overview

Firebird supports SSL/TLS encrypted connections for secure communication.

## Configuration

### Basic SSL Setup

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

### SSL Certificate Options

| Option | Description |
|--------|-------------|
| `ssl` | Enable SSL/TLS |
| `ssl_ca` | CA certificate file |
| `ssl_cert` | Client certificate file |
| `ssl_key` | Client key file |

### Full SSL Configuration

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

## Generating Certificates

### Self-Signed Certificates

```bash
# Generate CA key and certificate
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -out ca.pem

# Generate server key and certificate
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -days 365 -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out server.pem

# Generate client key and certificate
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr
openssl x509 -req -days 365 -in client.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out client.pem
```

## Firebird Server Configuration

### Enable SSL in Firebird

Edit `firebird.conf`:

```
WireCrypt = SSL
```

### Restart Firebird

```bash
sudo systemctl restart firebird3.0
```

## Testing SSL Connection

### Test with Python

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
print("SSL connection successful!")
backend.disconnect()
```

### Test with isql

```bash
isql-fb -user SYSDBA -password masterkey -host localhost -port 3050 -database /data/myapp.fdb
```

## Troubleshooting

### Common SSL Issues

1. **Certificate verification failed**
   - Check CA certificate path
   - Ensure certificates are not expired

2. **Connection refused**
   - Verify Firebird server has SSL enabled
   - Check firewall rules for SSL port

3. **Key/certificate mismatch**
   - Ensure key and certificate match
   - Regenerate certificates if needed

💡 *AI Prompt:* "How do I set up SSL/TLS for Firebird database connections?"