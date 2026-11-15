# tests/rhosocial/activerecord_firebird_test/feature/backend/adapters/test_json_adapter_hooks.py
"""DB-free tests for ``FirebirdJsonAdapter``'s optional ``default`` / ``object_hook``.

The hooks are forwarded to ``json.dumps`` / ``json.loads``. With ``default=None``
the adapter keeps its historical ``default=str`` fallback, so unsupported
objects still serialize through ``str()`` exactly as before.
"""

import json
from typing import Any

import pytest
from rhosocial.activerecord.backend.adapters.json_codec import (
    AdapterJSONCodec,
    register_type,
    unregister_type,
)

from rhosocial.activerecord.backend.impl.firebird.adapters import FirebirdJsonAdapter


class _Point:
    """Minimal neutral type used to prove the hooks reach ``json``."""

    json_type_tag = "demo_point_firebird"

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def to_json_value(self) -> Any:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_json_value(cls, value: Any) -> "_Point":
        return cls(int(value["x"]), int(value["y"]))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Point) and (self.x, self.y) == (other.x, other.y)


class _Opaque:
    """Only serializable through ``default=str``."""

    def __str__(self) -> str:
        return "opaque"


class TestNoHooks:
    """``default=None`` / ``object_hook=None`` reproduce the historical behaviour."""

    @pytest.fixture
    def adapter(self):
        return FirebirdJsonAdapter()

    def test_dict_round_trip(self, adapter):
        payload = {"a": [1, 2], "b": {"c": "x"}}
        stored = adapter.to_database(payload, dict)
        assert isinstance(stored, str)
        assert adapter.from_database(stored, dict) == payload

    def test_list_round_trip(self, adapter):
        payload = [1, "two", {"three": 3}]
        stored = adapter.to_database(payload, list)
        assert adapter.from_database(stored, list) == payload

    def test_unicode_still_not_ascii_escaped(self, adapter):
        assert "é" in adapter.to_database({"k": "é"}, dict)

    def test_historical_default_str_fallback_is_preserved(self, adapter):
        stored = adapter.to_database({"o": _Opaque()}, dict)
        assert stored == '{"o": "opaque"}'

    def test_plain_dict_and_list_decode_unchanged(self, adapter):
        payload = {"a": 1}
        assert adapter.from_database('{"a": 1}', dict) == payload
        assert adapter.from_database(payload, dict) is payload
        assert adapter.from_database([1, 2], list) == [1, 2]

    def test_bytes_and_string_inputs(self, adapter):
        assert adapter.from_database(b'{"k": 1}', dict) == {"k": 1}
        assert adapter.from_database("not json{", dict) == "not json{"

    def test_null_and_scalar_passthrough(self, adapter):
        assert adapter.to_database(None, dict) is None
        assert adapter.from_database(None, dict) is None
        assert adapter.from_database(5, dict) == 5

    def test_supported_types_unchanged(self, adapter):
        assert adapter.supported_types == {dict: [dict, list, str, bytes], list: [list, str, bytes]}


class TestCustomDefault:
    def test_custom_default_replaces_the_str_fallback(self):
        adapter = FirebirdJsonAdapter(default=lambda obj: str(obj).upper())
        assert adapter.to_database({"o": _Opaque()}, dict) == '{"o": "OPAQUE"}'

    def test_custom_default_does_not_affect_json_native_values(self):
        adapter = FirebirdJsonAdapter(default=lambda obj: "unused")
        assert adapter.to_database({"a": [1, None, True]}, dict) == '{"a": [1, null, true]}'

    def test_custom_default_keeps_ensure_ascii_false(self):
        adapter = FirebirdJsonAdapter(default=lambda obj: "unused")
        assert "é" in adapter.to_database({"k": "é"}, dict)

    def test_unsupported_default_type_still_raises(self):
        adapter = FirebirdJsonAdapter(default=object())
        with pytest.raises(TypeError):
            adapter.to_database({"o": _Opaque()}, dict)


class TestObjectHook:
    def test_object_hook_decodes_matching_dicts(self):
        def hook(value):
            if set(value) == {"x", "y"}:
                return _Point(value["x"], value["y"])
            return value

        adapter = FirebirdJsonAdapter(object_hook=hook)
        decoded = adapter.from_database('{"p": {"x": 1, "y": 2}}', dict)
        assert decoded == {"p": _Point(1, 2)}
        assert isinstance(decoded["p"], _Point)

    def test_object_hook_leaves_other_dicts_untouched(self):
        adapter = FirebirdJsonAdapter(
            object_hook=lambda value: _Point(0, 0) if "x" in value else value
        )
        assert adapter.from_database('{"a": 1, "b": [1, 2]}', dict) == {"a": 1, "b": [1, 2]}

    def test_object_hook_is_not_applied_to_dict_input(self):
        adapter = FirebirdJsonAdapter(object_hook=lambda value: _Point(0, 0))
        payload = {"x": 1, "y": 2}
        assert adapter.from_database(payload, dict) is payload

    def test_invalid_json_still_returns_original_text(self):
        adapter = FirebirdJsonAdapter(object_hook=lambda value: _Point(0, 0))
        assert adapter.from_database("not json{", dict) == "not json{"

    def test_matching_encode_and_decode_round_trip(self):
        def default(obj):
            if isinstance(obj, _Point):
                return obj.to_json_value()
            return str(obj)

        def hook(value):
            return _Point(value["x"], value["y"]) if set(value) == {"x", "y"} else value

        adapter = FirebirdJsonAdapter(default=default, object_hook=hook)
        stored = adapter.to_database({"p": _Point(1, 2)}, dict)
        assert stored == '{"p": {"x": 1, "y": 2}}'
        assert adapter.from_database(stored, dict) == {"p": _Point(1, 2)}


class TestAdapterJSONCodecInterop:
    def test_tagged_codec_round_trips_through_the_adapter(self):
        register_type("demo_point_firebird", _Point)
        try:
            codec = AdapterJSONCodec(tagged=True)
            adapter = FirebirdJsonAdapter(default=codec.default, object_hook=codec.object_hook)

            stored = adapter.to_database({"p": _Point(1, 2)}, dict)
            assert json.loads(stored) == {"p": {"x": 1, "y": 2, "__type__": "demo_point_firebird"}}

            decoded = adapter.from_database(stored, dict)
            assert isinstance(decoded["p"], _Point)
            assert decoded["p"] == _Point(1, 2)
        finally:
            unregister_type("demo_point_firebird")
