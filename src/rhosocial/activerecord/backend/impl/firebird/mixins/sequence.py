# src/rhosocial/activerecord/backend/impl/firebird/mixins/sequence.py
"""Firebird GENERATOR/SEQUENCE mixin."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_sequence import CreateSequenceExpression
    from ..expression.generator import GenIdExpression, NextValueForExpression


class FirebirdSequenceMixin:

    def format_create_sequence(
        self,
        expr: "CreateSequenceExpression",
    ) -> Tuple[str, tuple]:
        use_generator = getattr(expr, 'use_generator', False)
        if use_generator:
            return f"CREATE GENERATOR {self.format_identifier(expr.sequence_name)}", ()
        else:
            parts = [f"CREATE SEQUENCE {self.format_identifier(expr.sequence_name)}"]
            start_value = getattr(expr, 'start', None) or 1
            increment = getattr(expr, 'increment', None) or 1
            if start_value != 1:
                parts.append(f"START WITH {start_value}")
            if increment != 1:
                parts.append(f"INCREMENT BY {increment}")
            return ' '.join(parts), ()

    def format_gen_id(self, expr: "GenIdExpression") -> Tuple[str, tuple]:
        return (
            f"GEN_ID({self.format_identifier(expr._generator_name)}, {expr._step})",
            (),
        )

    def format_next_value_for(self, expr: "NextValueForExpression") -> Tuple[str, tuple]:
        return f"NEXT VALUE FOR {self.format_identifier(expr._sequence_name)}", ()

    def supports_sequence(self) -> bool:
        return True

    def supports_create_sequence(self) -> bool:
        return True

    def supports_alter_sequence(self) -> bool:
        return True

    def supports_create_generator(self) -> bool:
        return True