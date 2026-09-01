# firebird/protocols/alter_table_modifier_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class FirebirdAlterTableModifierSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_set_generated_action(self, action) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_restart_identity_action(self, action) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_set_increment_action(self, action) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_drop_identity_action(self, action) -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_set_position_action(self, action) -> Tuple[str, tuple]:
        ...  # pragma: no cover
