# firebird/protocols/routine_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class FirebirdRoutineSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_create_procedure_statement(self, expr) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_drop_routine_statement(self, expr) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_routine_params(self, params: List[Any]) -> str:
        ...  # pragma: no cover
    def format_routine_return_type(self, returns: Any) -> str:
        ...  # pragma: no cover
    def format_psql_body(self, body: str) -> str:
        ...  # pragma: no cover
