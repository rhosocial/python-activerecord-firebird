# src/rhosocial/activerecord/backend/impl/firebird/mixins/sequence.py
"""Firebird GENERATOR/SEQUENCE mixin.

Firebird 3.0 renamed ``GENERATOR`` to ``SEQUENCE`` and kept the old word as a
synonym, so both spellings are accepted and both name the same object kind.
``GEN_ID(...)`` and ``NEXT VALUE FOR`` name that same kind, and are rendered
through the schema-object layer with the DDL forms -- a generator name is an
object identity, not a string to be quoted.
"""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import Sequence

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_sequence import CreateSequenceExpression
    from ..expression.generator import GenIdExpression, NextValueForExpression


class FirebirdSequenceMixin:

    def format_create_sequence(
        self,
        expr: "CreateSequenceExpression",
    ) -> Tuple[str, tuple]:
        """Render CREATE SEQUENCE / CREATE GENERATOR, Firebird's word order.

        **Not the dispatched formatter.** ``CreateSequenceExpression.format_method``
        returns ``"format_create_sequence_statement"``, and that is the core
        ``SequenceMixin`` method, so a CREATE SEQUENCE never reaches this one --
        which is why the SQL it produces here (``CREATE SEQUENCE "GEN"``) differs
        from what the dialect actually emits (``CREATE SEQUENCE "GEN" NO CYCLE``).
        Nothing calls it either: no core protocol declares this name and no
        ``format_method`` in either tree returns it. It is kept because it is
        Firebird's documented ``CREATE GENERATOR`` spelling, which the core
        formatter has no way to produce; deleting it would remove the only place
        that spelling exists.

        The type check below therefore guards a direct call rather than the
        render path. The render path is guarded too, by the core
        ``format_create_sequence_statement``, and it is that one which refuses a
        wrong object kind in normal use.

        Raises:
            TypeError: ``CreateSequenceExpression.sequence`` is not a Sequence. A
                table would render as a well-formed CREATE SEQUENCE over that
                table's name, because the object carries its own format method and
                the dialect would reach ``format_table_object`` and get valid SQL
                naming the wrong kind of thing.
        """
        if not isinstance(expr.sequence, Sequence):
            raise TypeError(
                f"CreateSequenceExpression.sequence must be a Sequence, "
                f"got {type(expr.sequence).__name__}"
            )
        use_generator = getattr(expr, 'use_generator', False)
        # The Sequence object renders itself, so the DDL form and the reference
        # forms below agree on how the name is quoted.
        sequence_sql = expr.sequence.to_sql()[0]
        if use_generator:
            return f"CREATE GENERATOR {sequence_sql}", ()
        else:
            parts = [f"CREATE SEQUENCE {sequence_sql}"]
            start_value = getattr(expr, 'start', None) or 1
            increment = getattr(expr, 'increment', None) or 1
            if start_value != 1:
                parts.append(f"START WITH {start_value}")
            if increment != 1:
                parts.append(f"INCREMENT BY {increment}")
            return ' '.join(parts), ()

    def format_gen_id(self, expr: "GenIdExpression") -> Tuple[str, tuple]:
        generator_sql = Sequence(self, expr._generator_name).to_sql()[0]
        return f"GEN_ID({generator_sql}, {expr._step})", ()

    def format_next_value_for(self, expr: "NextValueForExpression") -> Tuple[str, tuple]:
        sequence_sql = Sequence(self, expr._sequence_name).to_sql()[0]
        return f"NEXT VALUE FOR {sequence_sql}", ()

    def supports_sequence(self) -> bool:
        return True

    def supports_create_sequence(self) -> bool:
        return True

    def supports_alter_sequence(self) -> bool:
        return True

    def supports_create_generator(self) -> bool:
        return True
