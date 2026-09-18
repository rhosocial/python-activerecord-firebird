# src/rhosocial/activerecord/backend/impl/firebird/mixins/upsert.py
"""Firebird upsert mixin."""


class FirebirdUpsertMixin:

    def supports_upsert(self) -> bool:
        return True

    def get_upsert_syntax_type(self) -> str:
        return "UPDATE OR INSERT"

    def supports_on_conflict_clause(self) -> bool:
        """Firebird has no ON CONFLICT clause form; upsert is UPDATE OR INSERT."""
        return False
