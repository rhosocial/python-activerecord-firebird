# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/types/test_get_type_adapters.py
"""Offline coverage for ``FirebirdBackend.get_type_adapters()``.

``get_type_adapters`` is a plain inventory over the backend's adapter registry;
exercising it needs no live server.
"""

import pytest
from rhosocial.activerecord.backend.type_adapter import TypeAdapterCatalogProtocol

from rhosocial.activerecord.backend.impl.firebird.backend import FirebirdBackend


def _adapter_key(adapter):
    adapter_class = type(adapter)
    return (adapter_class.__module__, adapter_class.__qualname__)


@pytest.fixture(scope="module")
def backend():
    return FirebirdBackend(database="not-used-offline.fdb")


class TestGetTypeAdapters:
    def test_backend_implements_catalog_protocol(self, backend):
        assert isinstance(backend, TypeAdapterCatalogProtocol)

    def test_returns_non_empty_list(self, backend):
        adapters = backend.get_type_adapters()
        assert isinstance(adapters, list)
        assert adapters

    def test_adapters_unique_by_class(self, backend):
        keys = [_adapter_key(adapter) for adapter in backend.get_type_adapters()]
        assert len(keys) == len(set(keys))

    def test_order_is_deterministic(self, backend):
        first = backend.get_type_adapters()
        second = backend.get_type_adapters()
        assert [_adapter_key(adapter) for adapter in first] == [
            _adapter_key(adapter) for adapter in second
        ]

    def test_returns_new_list_each_call(self, backend):
        first = backend.get_type_adapters()
        second = backend.get_type_adapters()
        assert first is not second

    def test_data_adapter_suggestions_still_available(self, backend):
        assert callable(backend.suggest_data_adapters)
        suggestion = backend.suggest_data_adapters()
        assert isinstance(suggestion.table, dict)
        assert suggestion.table
