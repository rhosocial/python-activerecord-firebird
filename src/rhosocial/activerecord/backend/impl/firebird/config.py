# src/rhosocial/activerecord/backend/impl/firebird/config.py
"""Firebird connection configuration."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from rhosocial.activerecord.backend.config import (
    ConnectionConfig,
    ConnectionPoolMixin,
    SSLMixin,
    CharsetMixin,
    TimezoneMixin,
    VersionMixin,
    LoggingMixin,
)


@dataclass
class FirebirdConnectionConfig(
    ConnectionConfig,
    ConnectionPoolMixin,
    SSLMixin,
    CharsetMixin,
    TimezoneMixin,
    VersionMixin,
    LoggingMixin,
):
    """Firebird connection configuration.

    Extends the base configuration with Firebird-specific options.

    Default port for Firebird is 3050.
    """

    port: int = 3050
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    charset: str = "UTF8"
    page_size: Optional[int] = None
    wire_compression: bool = False
    use_unicode: bool = True
    autocommit: bool = False
    timeout: Optional[int] = None

    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["port"] = self.port
        result["database"] = self.database
        result["username"] = self.username
        result["password"] = self.password
        result["charset"] = self.charset
        result["use_unicode"] = self.use_unicode
        result["autocommit"] = self.autocommit
        if self.role:
            result["role"] = self.role
        if self.page_size:
            result["page_size"] = self.page_size
        if self.wire_compression:
            result["wire_compression"] = self.wire_compression
        if self.timeout:
            result["timeout"] = self.timeout
        return result

    @classmethod
    def from_env(cls, prefix: str = "FIREBIRD_") -> "FirebirdConnectionConfig":
        import os

        env_values = {}

        mapping = {
            "HOST": "host",
            "PORT": "port",
            "DATABASE": "database",
            "USERNAME": "username",
            "PASSWORD": "password",
            "ROLE": "role",
            "CHARSET": "charset",
            "PAGE_SIZE": "page_size",
            "POOL_SIZE": "pool_size",
            "POOL_TIMEOUT": "pool_timeout",
            "AUTOCOMMIT": "autocommit",
            "WIRE_COMPRESSION": "wire_compression",
            "TIMEOUT": "timeout",
        }

        for env_key, config_key in mapping.items():
            full_key = f"{prefix}{env_key}"
            if full_key in os.environ:
                value = os.environ[full_key]
                if config_key in ("port", "page_size", "pool_size", "pool_timeout", "timeout"):
                    value = int(value)
                elif config_key in ("autocommit", "wire_compression", "use_unicode"):
                    value = value.lower() in ("true", "yes", "1", "on")
                env_values[config_key] = value

        return cls(**env_values)