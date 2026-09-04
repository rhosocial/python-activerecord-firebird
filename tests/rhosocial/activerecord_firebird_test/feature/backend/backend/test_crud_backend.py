from decimal import Decimal


class TestCRUDBackend:
    def test_connect(self, fb_backend):
        assert fb_backend._is_connected
        assert fb_backend.ping()

    def test_insert(self, fb_backend, setup_test_table):
        table = setup_test_table
        result = fb_backend.insert(table, {
            "name": "test1",
            "amount": Decimal("100.50"),
            "is_active": True,
        })
        assert result.affected_rows == 1

    def test_insert_with_returning(self, fb_backend, setup_test_table):
        table = setup_test_table
        result = fb_backend.insert(table, {
            "name": "test_return",
            "amount": Decimal("200.00"),
        }, returning_columns=["id", "name"])
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["name"] == "test_return"

    def test_select(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "select_test", "amount": Decimal("50")})
        result = fb_backend.execute(
            f'SELECT * FROM {table} WHERE name = ?',
            ("select_test",),
            fetch=True,
        )
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["name"] == "select_test"

    def test_update(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "update_test", "amount": Decimal("10")})
        result = fb_backend.update(
            table,
            {"amount": Decimal("99.99")},
            where_clause=('name = ?', ("update_test",)),
        )
        assert result.affected_rows == 1
        rows = fb_backend.execute(
            f'SELECT amount FROM {table} WHERE name = ?',
            ("update_test",),
            fetch=True,
        ).data
        assert rows[0]["amount"] == Decimal("99.99")

    def test_update_with_returning(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "upd_ret", "amount": Decimal("1")})
        result = fb_backend.update(
            table,
            {"name": "upd_ret_updated"},
            where_clause=('name = ?', ("upd_ret",)),
            returning_columns=["id", "name"],
        )
        assert result.data is not None
        assert result.data[0]["name"] == "upd_ret_updated"

    def test_delete(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "delete_test", "amount": Decimal("0")})
        result = fb_backend.delete(
            table,
            where_clause=('name = ?', ("delete_test",)),
        )
        assert result.affected_rows == 1
        rows = fb_backend.execute(
            f'SELECT COUNT(*) FROM {table} WHERE name = ?',
            ("delete_test",),
            fetch=True,
        ).data
        assert rows[0]["count"] == 0

    def test_delete_with_returning(self, fb_backend, setup_test_table):
        table = setup_test_table
        fb_backend.insert(table, {"name": "del_ret", "amount": Decimal("5")})
        result = fb_backend.delete(
            table,
            where_clause=('name = ?', ("del_ret",)),
            returning_columns=["id", "name"],
        )
        assert result.data is not None
        assert result.data[0]["name"] == "del_ret"

    def test_execute_many(self, fb_backend, setup_test_table):
        table = setup_test_table
        params = [
            ("bulk1", Decimal("1")),
            ("bulk2", Decimal("2")),
            ("bulk3", Decimal("3")),
        ]
        result = fb_backend.execute_many(
            f'INSERT INTO {table} (name, amount) VALUES (?, ?)',
            params,
        )
        assert result.affected_rows == 3

    def test_get_server_version(self, fb_backend):
        version = fb_backend.get_server_version()
        assert len(version) == 3
        assert version[0] >= 5

    def test_ping(self, fb_backend):
        assert fb_backend.ping(reconnect=False) is True

    def test_insert_multiple_rows(self, fb_backend, setup_test_table):
        table = setup_test_table
        for i in range(5):
            fb_backend.insert(table, {"name": f"multi_{i}", "amount": Decimal(i)})
        result = fb_backend.execute(
            f'SELECT COUNT(*) FROM {table}',
            fetch=True,
        )
        assert result.data[0]["count"] == 5
