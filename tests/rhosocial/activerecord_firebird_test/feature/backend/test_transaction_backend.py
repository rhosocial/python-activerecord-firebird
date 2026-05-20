import pytest
from decimal import Decimal


class TestTransactionBackend:
    def test_transaction_commit(self, fb_backend, setup_test_table):
        table = setup_test_table
        tm = fb_backend.transaction_manager
        tm.begin()
        try:
            fb_backend.insert(table, {"name": "tx_commit", "amount": Decimal("100")})
            tm.commit()
        except Exception:
            tm.rollback()
            raise
        rows = fb_backend.execute(
            f'SELECT COUNT(*) FROM {table} WHERE name = ?',
            ("tx_commit",),
            fetch=True,
        ).data
        assert rows[0]["count"] == 1

    def test_transaction_rollback(self, fb_backend, setup_test_table):
        table = setup_test_table
        tm = fb_backend.transaction_manager
        tm.begin()
        fb_backend.insert(table, {"name": "tx_rollback", "amount": Decimal("200")})
        tm.rollback()
        rows = fb_backend.execute(
            f'SELECT COUNT(*) FROM {table} WHERE name = ?',
            ("tx_rollback",),
            fetch=True,
        ).data
        assert rows[0]["count"] == 0

    def test_transaction_context_manager(self, fb_backend, setup_test_table):
        table = setup_test_table
        tm = fb_backend.transaction_manager
        with tm:
            fb_backend.insert(table, {"name": "tx_ctx", "amount": Decimal("300")})
        rows = fb_backend.execute(
            f'SELECT COUNT(*) FROM {table} WHERE name = ?',
            ("tx_ctx",),
            fetch=True,
        ).data
        assert rows[0]["count"] == 1

    def test_transaction_context_manager_rollback_on_error(self, fb_backend, setup_test_table):
        table = setup_test_table
        tm = fb_backend.transaction_manager
        try:
            with tm:
                fb_backend.insert(table, {"name": "tx_err", "amount": Decimal("400")})
                raise ValueError("force rollback")
        except ValueError:
            pass
        rows = fb_backend.execute(
            f'SELECT COUNT(*) FROM {table} WHERE name = ?',
            ("tx_err",),
            fetch=True,
        ).data
        assert rows[0]["count"] == 0

    def test_nested_transaction_savepoint(self, fb_backend, setup_test_table):
        table = setup_test_table
        tm = fb_backend.transaction_manager
        tm.begin()
        try:
            fb_backend.insert(table, {"name": "outer", "amount": Decimal("1")})
            tm.begin()
            fb_backend.insert(table, {"name": "inner", "amount": Decimal("2")})
            tm.rollback()
            fb_backend.insert(table, {"name": "after_inner", "amount": Decimal("3")})
            tm.commit()
        except Exception:
            tm.rollback()
            raise
        rows = fb_backend.execute(
            f'SELECT name FROM {table} ORDER BY id',
            fetch=True,
        ).data
        names = [r["name"] for r in rows]
        assert "outer" in names
        assert "inner" not in names
        assert "after_inner" in names

    def test_transaction_isolation(self, fb_backend, setup_test_table):
        table = setup_test_table
        tm = fb_backend.transaction_manager
        tm.begin()
        fb_backend.insert(table, {"name": "iso_test", "amount": Decimal("500")})
        conn2 = fb_backend.__class__(connection_config=fb_backend.config)
        conn2.connect()
        try:
            rows = conn2.execute(
                f'SELECT COUNT(*) FROM {table} WHERE name = ?',
                ("iso_test",),
                fetch=True,
            ).data
            assert rows[0]["count"] == 0
        finally:
            conn2.disconnect()
        tm.commit()

    def test_autocommit_mode(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "autocommit", "amount": Decimal("600")})
        conn2 = fb_backend.__class__(connection_config=fb_backend.config)
        conn2.connect()
        try:
            rows = conn2.execute(
                f'SELECT COUNT(*) FROM {table} WHERE name = ?',
                ("autocommit",),
                fetch=True,
            ).data
            assert rows[0]["count"] == 1
        finally:
            conn2.disconnect()
