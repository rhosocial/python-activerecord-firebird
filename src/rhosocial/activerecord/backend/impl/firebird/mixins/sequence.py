# src/rhosocial/activerecord/backend/impl/firebird/mixins/sequence.py
"""Firebird GENERATOR/SEQUENCE mixin.

Firebird 3.0 renamed ``GENERATOR`` to ``SEQUENCE`` and kept the old word as a
synonym, so both spellings are accepted and both name the same object kind.
``GEN_ID(...)`` and ``NEXT VALUE FOR`` name that same kind, and are rendered
through the schema-object layer with the DDL forms -- a generator name is an
object identity, not a string to be quoted.
"""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Sequence

from .version_boundaries import FIREBIRD_VERSION_BOUNDARIES, _norm_version

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_sequence import CreateSequenceExpression
    from ..expression.generator import GenIdExpression, NextValueForExpression


class FirebirdSequenceMixin:

    def format_create_sequence_statement(
        self,
        expr: "CreateSequenceExpression",
    ) -> Tuple[str, tuple]:
        """Render ``CREATE SEQUENCE`` / ``CREATE GENERATOR`` for Firebird.

        This is the dispatched formatter: ``CreateSequenceExpression.format_method``
        returns ``"format_create_sequence_statement"``, and ``FirebirdSequenceMixin``
        precedes ``SequenceMixin`` in the dialect bases, so a ``CREATE SEQUENCE``
        reaches this method rather than the core one. An earlier spelling of this
        method -- ``format_create_sequence`` -- was reachable by nothing, so the
        SQL written here never reached the server; the name is now the one the
        dispatch uses.

        Firebird's grammar is narrow (language reference, ``CREATE SEQUENCE``):

            CREATE {SEQUENCE | GENERATOR} name
              [START WITH start_value] [INCREMENT [BY] increment]

        ``START WITH`` and ``INCREMENT BY`` are the only options, so
        ``supports_sequence_start()`` and ``supports_sequence_increment()`` are
        the only option probes that answer ``True``. Every other option the
        expression can carry -- ``IF NOT EXISTS``, ``MINVALUE``, ``MAXVALUE``,
        ``CYCLE``, ``CACHE``, ``ORDER``, ``OWNED BY`` -- is refused with
        ``UnsupportedFeatureError`` naming it rather than dropped, because
        dropping the clause would silently change the statement's meaning.
        ``NO CYCLE`` is never emitted: Firebird's grammar has no such words, and
        ``supports_sequence_cycle()`` is ``False``.

        ``supports_sequence()`` is consulted first and unconditionally, and is
        version-gated at Firebird 3.0, the oldest version this backend declares
        support for. The ``SEQUENCE`` spelling itself is older -- the 2.5
        language reference already lists ``CREATE SEQUENCE`` as a synonym for
        ``CREATE GENERATOR`` -- so the gate tracks the declared floor rather than
        the grammar's introduction.

        ``CREATE GENERATOR`` is Firebird's documented legacy synonym for
        ``CREATE SEQUENCE``; both name the same object and accept the same
        ``START WITH`` / ``INCREMENT BY`` clauses. It is reached through the
        ``use_generator`` attribute, and the core formatter has no way to produce
        that spelling, which is why it stays here.

        Version notes (language reference, 3.0 vs 4.0+): in 3.0 ``START WITH``
        set the *current* value rather than the first value ``NEXT VALUE FOR``
        returns (CORE-6084), and a sequence created without ``START WITH``
        started at 0; from 4.0 the SQL-standard meaning is followed and the
        default start is 1. Negative increments likewise started at
        ``0 + increment`` in 3.0 and at 1 from 4.0. The two spellings this
        method emits are identical across those versions; only the server's
        interpretation of the values differs.

        Raises:
            TypeError: ``CreateSequenceExpression.sequence`` is not a Sequence. A
                table would render as a well-formed CREATE SEQUENCE over that
                table's name, because the object carries its own format method and
                the dialect would reach ``format_table_object`` and get valid SQL
                naming the wrong kind of thing.
            UnsupportedFeatureError: The dialect predates Firebird 3.0, or the
                expression asks for an option Firebird's grammar does not have.
        """
        if not isinstance(expr.sequence, Sequence):
            raise TypeError(
                f"CreateSequenceExpression.sequence must be a Sequence, "
                f"got {type(expr.sequence).__name__}"
            )
        if not self.supports_sequence():
            raise UnsupportedFeatureError(
                self.name, "CREATE SEQUENCE",
                f"{self.name} has no sequence object to create before version 3.0."
            )
        if expr.if_not_exists:
            if not self.supports_sequence_if_not_exists():
                raise UnsupportedFeatureError(
                    self.name, "CREATE SEQUENCE IF NOT EXISTS",
                    f"{self.name} does not support CREATE SEQUENCE IF NOT EXISTS."
                )
        if expr.minvalue is not None:
            if not self.supports_sequence_minvalue():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE MINVALUE",
                    f"{self.name} does not support the MINVALUE sequence option."
                )
        if expr.maxvalue is not None:
            if not self.supports_sequence_maxvalue():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE MAXVALUE",
                    f"{self.name} does not support the MAXVALUE sequence option."
                )
        if expr.cycle:
            if not self.supports_sequence_cycle():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE CYCLE",
                    f"{self.name} does not support the CYCLE sequence option."
                )
        if expr.cache is not None:
            if not self.supports_sequence_cache():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE CACHE",
                    f"{self.name} does not support the CACHE sequence option."
                )
        if expr.order:
            if not self.supports_sequence_order():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE ORDER",
                    f"{self.name} does not support the ORDER sequence option."
                )
        if expr.owned_by is not None:
            if not self.supports_sequence_owned_by():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE OWNED BY",
                    f"{self.name} does not support the OWNED BY sequence option."
                )

        use_generator = getattr(expr, 'use_generator', False)
        # The Sequence object renders itself, so the DDL form and the reference
        # forms below agree on how the name is quoted.
        sequence_sql = expr.sequence.to_sql()[0]
        keyword = "CREATE GENERATOR" if use_generator else "CREATE SEQUENCE"
        parts = [f"{keyword} {sequence_sql}"]
        # Firebird's defaults are START WITH 1 and INCREMENT BY 1, so a request
        # for either default is the same as omitting the clause. ``is not None``
        # rather than ``or`` keeps an explicit 0 a request for 0 rather than a
        # silent fall back to the default.
        if expr.start is not None:
            if not self.supports_sequence_start():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE START",
                    f"{self.name} does not support the START WITH sequence option."
                )
            if expr.start != 1:
                parts.append(f"START WITH {expr.start}")
        if expr.increment is not None:
            if not self.supports_sequence_increment():
                raise UnsupportedFeatureError(
                    self.name, "SEQUENCE INCREMENT",
                    f"{self.name} does not support the INCREMENT BY sequence option."
                )
            if expr.increment != 1:
                parts.append(f"INCREMENT BY {expr.increment}")
        return ' '.join(parts), ()

    def format_gen_id(self, expr: "GenIdExpression") -> Tuple[str, tuple]:
        generator_sql = Sequence(self, expr._generator_name).to_sql()[0]
        return f"GEN_ID({generator_sql}, {expr._step})", ()

    def format_next_value_for(self, expr: "NextValueForExpression") -> Tuple[str, tuple]:
        sequence_sql = Sequence(self, expr._sequence_name).to_sql()[0]
        return f"NEXT VALUE FOR {sequence_sql}", ()

    def supports_sequence(self) -> bool:
        """Whether Firebird has the sequence object.

        Gated at Firebird 3.0, the oldest version this backend declares support
        for. The ``SEQUENCE`` spelling predates that -- the 2.5 language
        reference already lists ``CREATE SEQUENCE`` as a synonym for
        ``CREATE GENERATOR`` -- so the gate tracks the declared floor rather than
        the grammar.
        """
        return _norm_version(self.version) >= FIREBIRD_VERSION_BOUNDARIES["SEQUENCE"]

    def supports_create_sequence(self) -> bool:
        return _norm_version(self.version) >= FIREBIRD_VERSION_BOUNDARIES["SEQUENCE"]

    def supports_drop_sequence(self) -> bool:
        return _norm_version(self.version) >= FIREBIRD_VERSION_BOUNDARIES["SEQUENCE"]

    def supports_alter_sequence(self) -> bool:
        return _norm_version(self.version) >= FIREBIRD_VERSION_BOUNDARIES["SEQUENCE"]

    def supports_sequence_if_not_exists(self) -> bool:
        """Firebird's ``CREATE SEQUENCE`` grammar has no ``IF NOT EXISTS``."""
        return False

    def supports_sequence_if_exists(self) -> bool:
        """Firebird's ``DROP SEQUENCE`` grammar has no ``IF EXISTS``."""
        return False

    def supports_sequence_start(self) -> bool:
        """``START WITH`` is one of the two clauses Firebird's grammar has.

        This describes the ``CREATE SEQUENCE ... START WITH`` clause. It does
        *not* describe ``ALTER SEQUENCE``: the ALTER grammar has no ``START``
        at all (the server answers ``Token unknown - START``), so
        :meth:`supports_alter_sequence_start` is the probe the ALTER formatter
        must consult instead of this one.
        """
        return True

    def supports_alter_sequence_start(self) -> bool:
        """Firebird's ``ALTER SEQUENCE`` grammar has no ``START`` clause.

        ``ALTER SEQUENCE`` can only ``RESTART [WITH]`` and change the
        ``INCREMENT [BY]``; ``START WITH`` belongs to ``CREATE SEQUENCE``
        alone. The two are different clauses, so the CREATE probe's ``True``
        must not be reused here -- ``ALTER SEQUENCE ... START WITH 5`` is a
        syntax error on the server.
        """
        return False

    def supports_sequence_increment(self) -> bool:
        """``INCREMENT [BY]`` is the other clause Firebird's grammar has."""
        return True

    def supports_sequence_minvalue(self) -> bool:
        return False

    def supports_sequence_maxvalue(self) -> bool:
        return False

    def supports_sequence_cycle(self) -> bool:
        """Firebird has no ``CYCLE`` / ``NO CYCLE`` words at all."""
        return False

    def supports_sequence_cache(self) -> bool:
        return False

    def supports_sequence_order(self) -> bool:
        return False

    def supports_sequence_owned_by(self) -> bool:
        return False

    def supports_create_generator(self) -> bool:
        """Firebird's legacy spelling of ``CREATE SEQUENCE``.

        ``GENERATOR`` predates the SQL-standard word and names the same object,
        so it is not version-gated with the sequence spellings.
        """
        return True
