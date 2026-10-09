# src/rhosocial/activerecord/backend/impl/firebird/mixins/json.py
"""Firebird has no JSON path functions, and this records why.

The standard pair — ``JSON_VALUE`` for a scalar and ``JSON_QUERY`` for a
document — is an open proposal on Firebird: tracker #5431, "SQL-compliant
JSON functions", is still pending in the v6 roadmap. A 6-snapshot server
answers ``Function unknown`` for ``JSON_VALUE``, and 5 and 3 do not have it
either. So there is no version to gate on: every released server refuses.

What Firebird does have is JSON *construction* — ``JSON_ARRAY``,
``JSON_OBJECT``, ``JSON_ARRAYAGG``, ``JSON_OBJECTAGG`` — which says nothing
about reading a path out of a document.

Without this, a JSON path reached the core default and came back as
``JSON_EXTRACT`` wrapped in ``JSON_UNQUOTE``, and Firebird has neither. The
core now refuses on the strength of ``supports_json_type()``, so the honest
answer here is the one that keeps a caller from shipping SQL the server
rejects.

If a Firebird release gains the functions, the work is a formatter emitting
``JSON_VALUE`` / ``JSON_QUERY`` plus a version gate here — and the probe above
turned on. Nothing else in the backend needs to change.
"""

# src/rhosocial/activerecord/backend/impl/firebird/mixins/json.py
class FirebirdJSONMixin:
    """Records that this dialect has no JSON path support at all."""

    def supports_json_path(self) -> bool:
        """No released Firebird can read a JSON path. See the module docstring.

        Named separately from supports_json_type because they answer different
        questions and would drift apart: Firebird has JSON construction from
        2.5 and no path functions in any release.
        """
        return False

    def supports_json_type(self) -> bool:
        """No released Firebird has JSON_VALUE or JSON_QUERY.

        See the module docstring: #5431 is still pending, and a 6-snapshot
        server answers "Function unknown". There is no version to gate on.
        """
        return False
