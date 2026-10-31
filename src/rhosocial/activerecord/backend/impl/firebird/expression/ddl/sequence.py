# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/sequence.py
"""Firebird's CREATE SEQUENCE statement with the legacy GENERATOR spelling.

Firebird 3.0 renamed ``GENERATOR`` to ``SEQUENCE`` and kept the old word as a
documented synonym, so both spellings name the same object and accept the
same clauses. Which word a statement writes is a decision the caller makes at
construction time, carried by this node's ``use_generator`` field. The
generic :class:`CreateSequenceStatement` declares no such field, and mounting
one on it from outside would be hidden state -- the formatter could not tell
a field the contract carries from one somebody attached after the fact.
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    CreateSequenceStatement,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.objects import Sequence


class FirebirdCreateSequenceStatement(CreateSequenceStatement):
    """A ``CREATE SEQUENCE`` that can also spell itself ``CREATE GENERATOR``.

    Keeps every parameter the generic statement carries and adds exactly one:
    ``use_generator`` selects the legacy keyword. The formatter the generic
    statement dispatches to (:meth:`format_create_sequence_statement`) renders
    this node too, and reads the field only after asking the node's kind.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        sequence: "Sequence",
        if_not_exists: bool = False,
        start: Optional[int] = None,
        increment: Optional[int] = None,
        minvalue: Optional[int] = None,
        maxvalue: Optional[int] = None,
        cycle: bool = False,
        no_cycle: bool = False,
        cache: Optional[int] = None,
        no_cache: bool = False,
        order: bool = False,
        no_order: bool = False,
        owned_by: Optional[str] = None,
        *,
        use_generator: bool = False,
    ):
        super().__init__(
            dialect,
            sequence,
            if_not_exists=if_not_exists,
            start=start,
            increment=increment,
            minvalue=minvalue,
            maxvalue=maxvalue,
            cycle=cycle,
            no_cycle=no_cycle,
            cache=cache,
            no_cache=no_cache,
            order=order,
            no_order=no_order,
            owned_by=owned_by,
        )
        #: Whether the statement spells the legacy ``CREATE GENERATOR``
        #: keyword rather than ``CREATE SEQUENCE``. A field of this node, not
        #: an attribute to mount on the generic statement.
        self.use_generator: bool = use_generator


__all__ = ["FirebirdCreateSequenceStatement"]
