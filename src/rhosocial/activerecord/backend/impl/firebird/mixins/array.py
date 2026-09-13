# src/rhosocial/activerecord/backend/impl/firebird/mixins/array.py
"""Firebird array mixin."""


class FirebirdArrayMixin:

    def supports_array_type(self) -> bool:
        return True
