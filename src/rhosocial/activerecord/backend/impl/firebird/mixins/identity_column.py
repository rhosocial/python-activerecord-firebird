# src/rhosocial/activerecord/backend/impl/firebird/mixins/identity_column.py
"""Firebird identity-column capability probes.

Firebird's server-generated column is the SQL-standard identity clause,
``GENERATED {ALWAYS|BY DEFAULT} AS IDENTITY``, available from Firebird 3.0.
The formatter is core's -- Firebird executes the standard render unchanged, so
this mixin declares only what the server accepts, probe by probe, and never
overrides the rendering itself.

Measured on Firebird 5.0.4 and 6.0.0 through the driver this suite uses:
``START WITH`` and ``INCREMENT BY`` execute; ``MINVALUE``, ``MAXVALUE`` and
``CYCLE`` / ``NO CYCLE`` are refused with ``Token unknown``. The ``False``
probes keep the refused options off the wire -- the core formatter raises
``UnsupportedFeatureError`` naming the option instead of dropping it.

``supports_auto_increment_column()`` answers for the *other* mechanism: the
parameterless ``AUTO_INCREMENT`` marker. Firebird has no such keyword; its
server-generated column is the identity clause, so the marker is refused rather
than rendered.
"""

from .version_boundaries import FIREBIRD_VERSION_BOUNDARIES, _norm_version


class FirebirdIdentityColumnMixin:
    """Firebird's answers to the core identity / auto-increment probes."""

    def supports_identity_column(self) -> bool:
        """Whether Firebird accepts ``GENERATED ... AS IDENTITY``.

        Gated at Firebird 3.0, the version that introduced the identity
        column; the 2.5 language reference has no such grammar.
        """
        return _norm_version(self.version) >= FIREBIRD_VERSION_BOUNDARIES["IDENTITY"]

    def supports_identity_generation_always(self) -> bool:
        """``GENERATED ALWAYS`` executes on Firebird 3.0+.

        Measured on 5.0.4 and 6.0.0. The server enforces the mode -- a
        user-supplied value for an ``ALWAYS`` column is rejected at INSERT --
        so the request is expressible as asked, with no downgrade to
        ``BY DEFAULT``.
        """
        return True

    def supports_identity_start(self) -> bool:
        """``START WITH`` executes inside the identity clause.

        Measured on 5.0.4 and 6.0.0; the option is part of Firebird's identity
        grammar.
        """
        return True

    def supports_identity_increment(self) -> bool:
        """``INCREMENT BY`` executes inside the identity clause.

        Measured on 5.0.4 and 6.0.0; the option is part of Firebird's identity
        grammar.
        """
        return True

    def supports_identity_minvalue(self) -> bool:
        """Firebird's identity clause has no ``MINVALUE``.

        Measured on 5.0.4 and 6.0.0: the server answers ``Token unknown -
        MINVALUE``. The core formatter refuses a requested bound by name
        rather than dropping it.
        """
        return False

    def supports_identity_maxvalue(self) -> bool:
        """Firebird's identity clause has no ``MAXVALUE``.

        Measured on 5.0.4 and 6.0.0: the server answers ``Token unknown -
        MAXVALUE``.
        """
        return False

    def supports_identity_cycle(self) -> bool:
        """Firebird's identity clause has no ``CYCLE`` / ``NO CYCLE``.

        Measured on 5.0.4 and 6.0.0: ``CYCLE`` is answered with ``Token
        unknown - CYCLE`` and ``NO CYCLE`` with ``Token unknown - NO``. Both
        spellings the expression can carry are refused.
        """
        return False

    def supports_auto_increment_column(self) -> bool:
        """Firebird has no bare ``AUTO_INCREMENT`` marker.

        Its server-generated column is the identity clause above, a different
        mechanism with its own parameter space; the marker is refused by name
        rather than rendered.
        """
        return False
