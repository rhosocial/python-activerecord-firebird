# src/rhosocial/activerecord/backend/impl/firebird/explain/types.py
"""Firebird EXPLAIN result types."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FirebirdExplainResult:
    """Firebird EXPLAIN PLAN result.

    Attributes:
        plan_text: Raw plan text from EXPLAIN PLAN FOR
        plan_lines: Parsed plan lines
        metadata: Additional plan metadata
    """
    plan_text: str = ""
    plan_lines: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.plan_lines and self.plan_text:
            self.plan_lines = [line.strip() for line in self.plan_text.split('\n') if line.strip()]

    @property
    def is_valid(self) -> bool:
        """Whether the plan contains valid data."""
        return bool(self.plan_text)


@dataclass
class FirebirdExplainPlanLine:
    """A single line in a Firebird query plan.

    Attributes:
        level: Indentation level
        text: Plan line text
        node_type: Type of plan node (NATURAL, INDEX, SORT, etc.)
        relation: Table or index name
    """
    level: int = 0
    text: str = ""
    node_type: Optional[str] = None
    relation: Optional[str] = None


__all__ = ["FirebirdExplainResult", "FirebirdExplainPlanLine"]