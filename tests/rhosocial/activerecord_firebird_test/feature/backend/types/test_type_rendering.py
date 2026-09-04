# tests/rhosocial/activerecord_firebird_test/feature/backend/types/test_type_rendering.py
"""Offline FB4 data-type gate snapshots for the Firebird dialect.

Covers the FB4 data-type version gate on both sides (mixins/types.py):
TIMESTAMP/TIME WITH TIME ZONE, DECFLOAT and INT128 must render on any
4.0 dialect shape (including the two-component ``(4, 0)`` pin) and raise
``UnsupportedFeatureError`` on a 3.0 dialect. Exact to_sql() snapshots,
no database connection.
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.types import (
    FirebirdDecFloatType,
    FirebirdInt128Type,
    FirebirdTimeStampTzType,
    FirebirdTimeTzType,
)


class TestFB4TypeGateSupportedSide:
    """FB4-gated types must render on any 4.0 dialect shape.

    The ``(4, 0)`` variants pin F4: a two-component version tuple compares
    less than ``(4, 0, 0)``, so every gate must normalize before comparing.
    """

    @pytest.mark.parametrize("version", [(4, 0, 0), (4, 0)])
    @pytest.mark.parametrize("data_type,expected", [
        (FirebirdTimeStampTzType(), "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType(), "TIME WITH TIME ZONE"),
        (FirebirdDecFloatType(precision=16), "DECFLOAT(16)"),
        (FirebirdDecFloatType(precision=34), "DECFLOAT(34)"),
        (FirebirdInt128Type(), "INT128"),
    ])
    def test_fb4_types_render_on_4_0(self, version, data_type, expected):
        sql = FirebirdDialect(version).format_data_type(data_type)
        assert sql == (expected, ())
        assert data_type.to_sql(FirebirdDialect(version)) == (expected, ())

    def test_support_flags_agree_with_rendering(self):
        for version in ((4, 0, 0), (4, 0)):
            assert FirebirdDialect(version).supports_decfloat() is True


class TestFB4TypeGateUnsupportedSide:
    """The same types must raise on a (3, 0, 0) dialect."""

    @pytest.mark.parametrize("data_type,feature", [
        (FirebirdTimeStampTzType(), "TIMESTAMP WITH TIME ZONE"),
        (FirebirdTimeTzType(), "TIME WITH TIME ZONE"),
        (FirebirdDecFloatType(), "DECFLOAT"),
        (FirebirdInt128Type(), "INT128"),
    ])
    def test_fb4_types_raise_on_3_0(self, data_type, feature):
        dialect = FirebirdDialect((3, 0))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(data_type)
        assert feature in str(excinfo.value)

    def test_decfloat_flag_off_on_3_0(self):
        assert FirebirdDialect((3, 0)).supports_decfloat() is False
