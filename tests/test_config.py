# tests/test_config.py
"""Tests for FirebirdConnectionConfig."""



from rhosocial.activerecord.backend.impl.firebird import FirebirdConnectionConfig


class TestFirebirdConnectionConfig:
    """FirebirdConnectionConfig tests."""

    def test_default_values(self):
        config = FirebirdConnectionConfig()
        assert config.host == "localhost"
        assert config.port == 3050
        assert config.charset == "UTF8"
        assert config.use_unicode is True
        assert config.autocommit is False
        assert config.wire_compression is False

    def test_custom_values(self):
        config = FirebirdConnectionConfig(
            host="db.example.com",
            port=3051,
            database="/path/to/db.fdb",
            username="test_user",
            password="test_pass",
            role="ADMIN",
            page_size=16384,
            charset="ISO8859_1",
            wire_compression=True,
        )
        assert config.host == "db.example.com"
        assert config.port == 3051
        assert config.database == "/path/to/db.fdb"
        assert config.username == "test_user"
        assert config.password == "test_pass"
        assert config.role == "ADMIN"
        assert config.page_size == 16384
        assert config.charset == "ISO8859_1"
        assert config.wire_compression is True

    def test_to_dict(self):
        config = FirebirdConnectionConfig(
            host="192.168.1.1",
            port=3050,
            database="test.fdb",
            username="SYSDBA",
            password="masterkey",
        )
        d = config.to_dict()
        assert d["host"] == "192.168.1.1"
        assert d["port"] == 3050
        assert d["database"] == "test.fdb"
        assert d["username"] == "SYSDBA"
        assert d["password"] == "masterkey"
        assert d["charset"] == "UTF8"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("FIREBIRD_HOST", "firebird.example.com")
        monkeypatch.setenv("FIREBIRD_PORT", "3051")
        monkeypatch.setenv("FIREBIRD_DATABASE", "/db/test.fdb")
        monkeypatch.setenv("FIREBIRD_USERNAME", "admin")
        monkeypatch.setenv("FIREBIRD_PASSWORD", "secret")
        monkeypatch.setenv("FIREBIRD_CHARSET", "UTF8")
        monkeypatch.setenv("FIREBIRD_AUTOCOMMIT", "true")
        monkeypatch.setenv("FIREBIRD_ROLE", "APP_ROLE")

        config = FirebirdConnectionConfig.from_env()
        assert config.host == "firebird.example.com"
        assert config.port == 3051
        assert config.database == "/db/test.fdb"
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.charset == "UTF8"
        assert config.autocommit is True
        assert config.role == "APP_ROLE"

    def test_custom_prefix(self, monkeypatch):
        monkeypatch.setenv("FB_HOST", "fb.local")
        config = FirebirdConnectionConfig.from_env(prefix="FB_")
        assert config.host == "fb.local"

    def test_clone(self):
        config = FirebirdConnectionConfig(host="old.example.com", port=3050)
        cloned = config.clone(host="new.example.com")
        assert cloned.host == "new.example.com"
        assert cloned.port == 3050
        assert config.host == "old.example.com"

    def test_options(self):
        config = FirebirdConnectionConfig()
        assert isinstance(config.options, dict)