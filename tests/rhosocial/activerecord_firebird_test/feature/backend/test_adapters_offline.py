# tests/rhosocial/activerecord_firebird_test/feature/backend/test_adapters_offline.py
"""Offline round-trip tests for every Firebird SQLTypeAdapter.

Each adapter is exercised in both directions (to_database / from_database)
covering None, empty values, BLOB sub-type adapters (binary vs. text),
JSON-encoded arrays and escape-direction passthrough for strings.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from rhosocial.activerecord.backend.impl.firebird.adapters import (
    FirebirdBlobAdapter,
    FirebirdBooleanAdapter,
    FirebirdDateAdapter,
    FirebirdDatetimeAdapter,
    FirebirdDecimalAdapter,
    FirebirdJsonAdapter,
    FirebirdTextBlobAdapter,
    FirebirdTimeAdapter,
    FirebirdUUIDAdapter,
    firebird_adapters,
)


class TestFirebirdBlobAdapter:
    def test_supported_types(self):
        assert FirebirdBlobAdapter().supported_types == {bytes: [bytes]}

    def test_to_database_binary_sub_type_values(self):
        adapter = FirebirdBlobAdapter()
        assert adapter.to_database(None, bytes) is None
        assert adapter.to_database(b"\x00\xff", bytes) == b"\x00\xff"
        assert adapter.to_database(bytearray(b"ab"), bytes) == b"ab"
        assert adapter.to_database(b"", bytes) == b""

    def test_to_database_rejects_non_binary(self):
        with pytest.raises(ValueError):
            FirebirdBlobAdapter().to_database("text", bytes)

    def test_from_database_binary_sub_type_values(self):
        adapter = FirebirdBlobAdapter()
        assert adapter.from_database(None, bytes) is None
        assert adapter.from_database(b"\x01\x02", bytes) == b"\x01\x02"
        assert adapter.from_database(bytearray(b"xy"), bytes) == b"xy"
        assert adapter.from_database("zz", bytes) == b"zz"
        assert adapter.from_database(memoryview(b"q"), bytes) == b"q"


class TestFirebirdTextBlobAdapter:
    def test_supported_types(self):
        assert FirebirdTextBlobAdapter().supported_types == {str: [str]}

    def test_round_trip_text_sub_type(self):
        adapter = FirebirdTextBlobAdapter()
        assert adapter.to_database(None, str) is None
        payload = "héllo wörld"
        stored = adapter.to_database(payload, str)
        assert adapter.from_database(stored, str) == payload

    def test_escape_direction_is_passthrough_without_unescaping(self):
        adapter = FirebirdTextBlobAdapter()
        raw = "admin'-- \\n \"quoted\""
        assert adapter.to_database(raw, str) == raw
        assert adapter.from_database(adapter.to_database(raw, str), str) == raw

    def test_trailing_whitespace_preserved(self):
        adapter = FirebirdTextBlobAdapter()
        padded = "value   \n"
        assert adapter.from_database(padded, str) == padded

    def test_from_database_bytes_variants(self):
        adapter = FirebirdTextBlobAdapter()
        assert adapter.from_database(b"abc", str) == "abc"
        assert adapter.from_database(bytearray(b"de"), str) == "de"
        assert adapter.from_database(12, str) == "12"


class TestFirebirdBooleanAdapter:
    def test_native_integer_binding(self):
        adapter = FirebirdBooleanAdapter()
        assert adapter.to_database(True, bool) == 1
        assert adapter.to_database(False, bool) == 0
        assert adapter.to_database(None, bool) is None

    def test_char_binding_variant(self):
        adapter = FirebirdBooleanAdapter(use_char=True)
        assert adapter.to_database(True, bool) == "T"
        assert adapter.to_database(False, bool) == "F"

    @pytest.mark.parametrize("stored,expected", [
        (True, True), (False, False), (None, None),
        (1, True), (0, False),
        ("T", True), ("true", True), ("Y", True), ("yes", True), ("1", True),
        ("F", False), ("no", False), ("0", False), ("", False),
        (b"T", True), (b"N", False),
    ])
    def test_from_database_truth_table(self, stored, expected):
        result = FirebirdBooleanAdapter().from_database(stored, bool)
        if expected is None:
            assert result is None
        else:
            assert result is expected


class TestFirebirdDecimalAdapter:
    @pytest.mark.parametrize("value,expected", [
        (Decimal("1.25"), Decimal("1.25")),
        (1.5, Decimal("1.5")),
        (7, Decimal("7")),
        ("3.14", Decimal("3.14")),
    ])
    def test_to_database_conversions(self, value, expected):
        assert FirebirdDecimalAdapter().to_database(value, Decimal) == expected

    def test_to_database_none_and_invalid(self):
        adapter = FirebirdDecimalAdapter()
        assert adapter.to_database(None, Decimal) is None
        with pytest.raises(ValueError):
            adapter.to_database([], Decimal)

    @pytest.mark.parametrize("value,expected", [
        (Decimal("9.99"), Decimal("9.99")),
        (9.99, Decimal("9.99")),
        (42, Decimal("42")),
        ("0.5", Decimal("0.5")),
        (b"2.75", Decimal("2.75")),
    ])
    def test_from_database_conversions(self, value, expected):
        assert FirebirdDecimalAdapter().from_database(value, Decimal) == expected

    def test_from_database_none_and_invalid(self):
        adapter = FirebirdDecimalAdapter()
        assert adapter.from_database(None, Decimal) is None
        with pytest.raises(ValueError):
            adapter.from_database(object(), Decimal)


class TestFirebirdDateAdapter:
    def test_to_database(self):
        adapter = FirebirdDateAdapter()
        assert adapter.to_database(date(2024, 5, 6), date) == date(2024, 5, 6)
        assert adapter.to_database(datetime(2024, 5, 6, 7, 8, 9), date) == date(2024, 5, 6)
        assert adapter.to_database("2024-05-06", date) == date(2024, 5, 6)
        assert adapter.to_database(None, date) is None

    def test_to_database_invalid_raises(self):
        with pytest.raises(ValueError):
            FirebirdDateAdapter().to_database(20240506, date)

    def test_from_database(self):
        adapter = FirebirdDateAdapter()
        assert adapter.from_database(date(2000, 1, 2), date) == date(2000, 1, 2)
        assert adapter.from_database(datetime(2000, 1, 2, 3, 4), date) == date(2000, 1, 2)
        assert adapter.from_database("2000-01-02", date) == date(2000, 1, 2)
        assert adapter.from_database(b"2000-01-02", date) == date(2000, 1, 2)
        assert adapter.from_database(None, date) is None


class TestFirebirdTimeAdapter:
    def test_to_database(self):
        adapter = FirebirdTimeAdapter()
        assert adapter.to_database(time(13, 30, 5), time) == time(13, 30, 5)
        assert adapter.to_database(datetime(2024, 1, 1, 8, 0, 0), time) == time(8, 0, 0)
        assert adapter.to_database("08:15:45", time) == time(8, 15, 45)
        assert adapter.to_database(timedelta(hours=13, minutes=30, seconds=5), time) == time(13, 30, 5)
        assert adapter.to_database(None, time) is None

    def test_from_database(self):
        adapter = FirebirdTimeAdapter()
        assert adapter.from_database(time(1, 2, 3), time) == time(1, 2, 3)
        assert adapter.from_database(timedelta(seconds=45296), time) == time(12, 34, 56)
        assert adapter.from_database(datetime(2024, 1, 1, 6, 30), time) == time(6, 30)
        assert adapter.from_database("06:07:08", time) == time(6, 7, 8)
        assert adapter.from_database(b"01:02:03", time) == time(1, 2, 3)
        assert adapter.from_database(None, time) is None

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            FirebirdTimeAdapter().to_database(3600, time)


class TestFirebirdDatetimeAdapter:
    def test_naive_datetime_stored_as_is(self):
        naive = datetime(2024, 1, 2, 3, 4, 5, 120000)
        assert FirebirdDatetimeAdapter(store_as_utc=False).to_database(naive, datetime) == naive

    def test_aware_datetime_normalized_to_utc_and_stripped(self):
        aware = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        stored = FirebirdDatetimeAdapter().to_database(aware, datetime)
        assert stored == datetime(2024, 1, 2, 10, 0, 0)
        assert stored.tzinfo is None

    def test_microseconds_truncated_to_firebird_precision(self):
        value = datetime(2024, 1, 2, 3, 4, 5, 123456)
        assert FirebirdDatetimeAdapter().to_database(value, datetime) == datetime(2024, 1, 2, 3, 4, 5, 120000)

    def test_to_database_string_and_invalid(self):
        adapter = FirebirdDatetimeAdapter()
        assert adapter.to_database("2024-01-02 03:04:05", datetime) == datetime(2024, 1, 2, 3, 4, 5)
        assert adapter.to_database(None, datetime) is None
        with pytest.raises(ValueError):
            adapter.to_database([1], datetime)

    def test_from_database_naive_gets_utc(self):
        loaded = FirebirdDatetimeAdapter().from_database(datetime(2024, 1, 2, 3, 4, 5), datetime)
        assert loaded.tzinfo == timezone.utc

    def test_from_database_aware_kept(self):
        aware = datetime(2024, 1, 2, tzinfo=timezone.utc)
        assert FirebirdDatetimeAdapter().from_database(aware, datetime) is aware

    def test_from_database_other_shapes(self):
        adapter = FirebirdDatetimeAdapter()
        assert adapter.from_database(date(2024, 1, 2), datetime) == datetime(2024, 1, 2, tzinfo=timezone.utc)
        assert adapter.from_database("2024-01-02 03:04:05", datetime) == datetime(2024, 1, 2, 3, 4, 5)
        assert adapter.from_database(b"2024-01-02 03:04:05", datetime) == datetime(2024, 1, 2, 3, 4, 5)
        assert adapter.from_database(1700000000.5, datetime).year == 2023
        assert adapter.from_database(None, datetime) is None

    def test_from_database_invalid_raises(self):
        with pytest.raises(ValueError):
            FirebirdDatetimeAdapter().from_database({"x": 1}, datetime)


class TestFirebirdUUIDAdapter:
    def test_binary_format_round_trip(self):
        adapter = FirebirdUUIDAdapter()
        value = UUID(int=42)
        stored = adapter.to_database(value, bytes)
        assert isinstance(stored, bytes) and len(stored) == 16
        assert adapter.from_database(stored, bytes) == value

    def test_string_input_binds_as_bytes_by_default(self):
        adapter = FirebirdUUIDAdapter()
        assert adapter.to_database(str(UUID(int=42)), bytes) == UUID(int=42).bytes

    def test_string_format_variant(self):
        adapter = FirebirdUUIDAdapter(use_string_format=True)
        value = UUID(int=42)
        assert adapter.to_database(value, str) == str(value)
        assert adapter.from_database(adapter.to_database(value, str), str) == value

    def test_from_database_shapes(self):
        adapter = FirebirdUUIDAdapter()
        value = UUID(int=7)
        assert adapter.from_database(value, bytes) is value
        assert adapter.from_database(str(value), bytes) == value
        assert adapter.from_database(str(value).encode("ascii"), bytes) == value
        assert adapter.from_database(None, bytes) is None

    def test_invalid_raises(self):
        adapter = FirebirdUUIDAdapter()
        with pytest.raises(ValueError):
            adapter.to_database(123, bytes)
        with pytest.raises(ValueError):
            adapter.from_database(b"zz", bytes)


class TestFirebirdJsonAdapter:
    def test_dict_round_trip(self):
        adapter = FirebirdJsonAdapter()
        payload = {"a": [1, 2], "b": {"c": "x"}}
        stored = adapter.to_database(payload, dict)
        assert isinstance(stored, str)
        assert adapter.from_database(stored, dict) == payload

    def test_array_round_trip(self):
        adapter = FirebirdJsonAdapter()
        payload = [1, "two", {"three": 3}]
        stored = adapter.to_database(payload, list)
        assert adapter.from_database(stored, list) == payload

    def test_unicode_not_ascii_escaped(self):
        stored = FirebirdJsonAdapter().to_database({"k": "é"}, dict)
        assert "é" in stored

    def test_from_database_passthroughs(self):
        adapter = FirebirdJsonAdapter()
        assert adapter.from_database(None, dict) is None
        assert adapter.from_database({"already": 1}, dict) == {"already": 1}
        assert adapter.from_database('{"k": 1}', dict) == {"k": 1}
        assert adapter.from_database(b'{"k": 1}', dict) == {"k": 1}
        assert adapter.from_database("not json{", dict) == "not json{"
        assert adapter.from_database(5, dict) == 5

    def test_scalar_serialized_as_string(self):
        assert FirebirdJsonAdapter().to_database(5, dict) == "5"


class TestAdapterRegistry:
    def test_registry_covers_all_adapters(self):
        registered = {entry[0] for entry in firebird_adapters}
        assert registered == {
            FirebirdBlobAdapter,
            FirebirdTextBlobAdapter,
            FirebirdBooleanAdapter,
            FirebirdDateAdapter,
            FirebirdTimeAdapter,
            FirebirdDatetimeAdapter,
            FirebirdDecimalAdapter,
            FirebirdUUIDAdapter,
            FirebirdJsonAdapter,
        }
