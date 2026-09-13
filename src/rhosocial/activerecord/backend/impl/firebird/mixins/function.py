# src/rhosocial/activerecord/backend/impl/firebird/mixins/function.py
"""Firebird function support mixin."""

from typing import Dict

from .version_boundaries import _norm_version


class FirebirdFunctionMixin:

    _FIREBIRD_FUNCTION_VERSIONS = {
        "gen_uuid": ((2, 5, 0), None),
        "uuid_to_char": ((3, 0, 0), None),
        "char_to_uuid": ((3, 0, 0), None),
        "list": ((2, 5, 0), None),
        "dateadd": ((2, 5, 0), None),
        "datediff": ((2, 5, 0), None),
        "replace": ((2, 5, 0), None),
        "position": ((2, 5, 0), None),
        "iif": ((2, 5, 0), None),
        "decode": ((2, 5, 0), None),
        "lpad": ((2, 5, 0), None),
        "rpad": ((2, 5, 0), None),
    }

    def supports_functions(self) -> Dict[str, bool]:
        from rhosocial.activerecord.backend.expression.functions import __all__ as core_functions
        expression_constructors = {
            "xmlagg",
            "xmlattributes",
            "xmlcomment",
            "xmlconcat",
            "xmlelement",
            "xmlexists",
            "xmlforest",
            "xmlparse",
            "xmlpi",
            "xmlquery",
            "xmlroot",
            "xmlserialize",
            "xmltable",
        }
        result = {}
        for func_name in core_functions:
            if func_name not in expression_constructors:
                result[func_name] = True
        for func_name, (_min_ver, _max_ver) in self._FIREBIRD_FUNCTION_VERSIONS.items():
            result[func_name] = self._is_firebird_function_supported(func_name)
        return result

    def _is_firebird_function_supported(self, func_name: str) -> bool:
        version_range = self._FIREBIRD_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True
        min_version, max_version = version_range
        if min_version is not None and _norm_version(self.version) < min_version:
            return False
        if max_version is not None and _norm_version(self.version) > max_version:
            return False
        return True
