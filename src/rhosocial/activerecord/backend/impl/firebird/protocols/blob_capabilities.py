# firebird/protocols/blob_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class FirebirdBlobSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_blob_column(self, column_name: str, sub_type: int=0, segment_size: int=65536, character_set: Optional[str]=None) -> str:
        ...  # pragma: no cover
