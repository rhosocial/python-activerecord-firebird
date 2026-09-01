# firebird/protocols/dml_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class FirebirdDMLOperationSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_insert_statement(self, expr) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_update_statement(self, expr) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_delete_statement(self, expr) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_execute_statement(self, expr) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_autonomous_transaction_do(self, block: str) -> Tuple[str, tuple]:
        ...  # pragma: no cover
