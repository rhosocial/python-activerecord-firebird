# src/rhosocial/activerecord/backend/impl/firebird/mixins/array.py
"""Firebird array mixin.

Firebird array columns and array *expressions* are two different features,
and this backend supports the first without supporting the second, so the
three ``ArraySupport`` probes do not all agree.
"""


class FirebirdArrayMixin:

    def supports_array_type(self) -> bool:
        """Firebird has array column types, so this is ``True``.

        The language reference devotes a section to them — "3.8. Array Types",
        present in the 2.5, 4.0 and 5.0 references alike — and shows

            CREATE TABLE SAMPLE_ARR (
              ID INTEGER NOT NULL PRIMARY KEY,
              ARR_INT INTEGER [4]
            );

        with ``INTEGER [0:3, 0:3]`` for two dimensions, ``[lo:hi]`` for
        explicit bounds and subscripts 1-based by default. They predate the
        time-zone types: this is a Firebird 2 feature, present in every version
        this backend targets, so the answer carries no version gate. The
        element type must be a simple type — a BLOB or an ARRAY may not be the
        element — and the value is stored as a BLOB sub-type, which is a
        storage detail and does not make the column a BLOB.

        Being unable to *render* such a column from :class:`ArrayType` is a
        separate, honest gap: Firebird's grammar requires the bounds as part of
        the type and ``ArrayType`` carries only a dimension count. See
        ``FirebirdTypeSupportMixin.suggested_data_types``.

        Note what this does **not** say: ``supports_array_constructor()`` and
        ``supports_array_access()`` stay ``False`` because this backend's
        ``ArrayExpression`` renderer emits the cross-vendor ``ARRAY[...]``
        spelling that Firebird's grammar does not have, and
        ``FirebirdUnsupportedFeaturesMixin.format_array_expression`` refuses
        it rather than emitting SQL the server rejects.
        """
        return True
