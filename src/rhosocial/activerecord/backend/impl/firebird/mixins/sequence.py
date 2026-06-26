# src/rhosocial/activerecord/backend/impl/firebird/mixins/sequence.py
"""Firebird GENERATOR/SEQUENCE mixin."""

from typing import Tuple


class FirebirdSequenceMixin:

    def format_create_sequence(
        self,
        sequence_name: str,
        start_value: int = 1,
        increment: int = 1,
        use_generator: bool = False,
    ) -> Tuple[str, tuple]:
        if use_generator:
            return f"CREATE GENERATOR {self.format_identifier(sequence_name)}", ()
        else:
            parts = [f"CREATE SEQUENCE {self.format_identifier(sequence_name)}"]
            if start_value != 1:
                parts.append(f"START WITH {start_value}")
            if increment != 1:
                parts.append(f"INCREMENT BY {increment}")
            return ' '.join(parts), ()

    def format_gen_id(self, generator_name: str, step: int = 1) -> Tuple[str, tuple]:
        return f"GEN_ID({self.format_identifier(generator_name)}, {step})", ()

    def format_next_value_for(self, sequence_name: str) -> Tuple[str, tuple]:
        return f"NEXT VALUE FOR {self.format_identifier(sequence_name)}", ()