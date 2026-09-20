# src/rhosocial/activerecord/backend/impl/firebird/expression/create_table.py
"""Firebird-specific CREATE TABLE expression.

Firebird adds two table-creation clauses with no generic equivalent:

* ``on_commit_delete`` -- ``ON COMMIT DELETE ROWS`` (``True``) or
  ``ON COMMIT PRESERVE ROWS`` (``False``) for global temporary tables.
* ``external_file`` -- ``EXTERNAL FILE '<path>'`` for external tables.

They live on ``FirebirdCreateTableExpression`` (deriving the generic
``CreateTableExpression``) and are rendered by the Firebird
``format_create_table_statement`` override, which accepts both the generic and
the Firebird-specific instance.
"""

from typing import TYPE_CHECKING, Any, List, Optional

from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableExpression,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.statements.ddl_table import (
        ColumnDefinition,
        CreateTableOptions,
        IndexDefinition,
        StorageOptionsExpression,
        TableConstraint,
    )
    from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
        PartitionClause,
    )


class FirebirdCreateTableExpression(CreateTableExpression):
    """A Firebird CREATE TABLE statement extending the generic one.

    Adds the Firebird-only ``on_commit_delete`` / ``external_file`` table
    clauses.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        columns: List["ColumnDefinition"],
        indexes: Optional[List["IndexDefinition"]] = None,
        table_constraints: Optional[List["TableConstraint"]] = None,
        temporary: bool = False,
        if_not_exists: bool = False,
        inherits: Optional[List[str]] = None,
        tablespace: Optional[str] = None,
        storage_options: Optional["StorageOptionsExpression"] = None,
        *,
        partition: Optional["PartitionClause"] = None,
        table_options: Optional["CreateTableOptions"] = None,
        on_commit_delete: Optional[bool] = None,
        external_file: Optional[str] = None,
    ):
        super().__init__(
            dialect,
            table,
            columns,
            indexes=indexes,
            table_constraints=table_constraints,
            temporary=temporary,
            if_not_exists=if_not_exists,
            inherits=inherits,
            tablespace=tablespace,
            storage_options=storage_options,
            partition=partition,
            table_options=table_options,
        )
        self.on_commit_delete = on_commit_delete
        self.external_file = external_file


__all__ = [
    "FirebirdCreateTableExpression",
]
