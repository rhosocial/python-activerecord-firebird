# tests/providers/basic.py
import os
import sys
import logging
from typing import Type, List, Tuple, Optional, Set

import pytest
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.type_adapter import BaseSQLTypeAdapter
from rhosocial.activerecord.testsuite.utils import select_fixture

from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    User as UserBase, TypeCase as TypeCaseBase,
    ValidatedFieldUser as ValidatedFieldUserBase,
    TypeTestModel as TypeTestModelBase, ValidatedUser as ValidatedUserBase,
    TypeAdapterTest as TypeAdapterTestBase, YesOrNoBooleanAdapter,
    MappedUser as MappedUserBase, MappedPost as MappedPostBase,
    MappedComment as MappedCommentBase,
    ColumnMappingModel as ColumnMappingModelBase,
    MixedAnnotationModel as MixedAnnotationModelBase,
    PydanticValidatedModel as PydanticValidatedModelBase,
    BulkUser as BulkUserBase,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    OrderItem as CompositeOrderItem,
    StoreInventory as StoreInventoryModel,
    Order as OrderModel,
    MappedOrderItem as MappedOrderItemModel,
    Product as ProductModel,
    ProductFormA as ProductFormAModel,
    ProductWithProxy as ProductWithProxyModel,
    ProductWithColumnAndAdapter as ProductWithColumnAndAdapterModel,
)

from rhosocial.activerecord.testsuite.feature.basic.interfaces import (
    BasicProviderBase,
    IBasicSyncProvider,
)
from rhosocial.activerecord.testsuite.core.protocols import WorkerTestProtocol
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


User = _select_model_class(UserBase, None, None, None, "User")
TypeCase = _select_model_class(TypeCaseBase, None, None, None, "TypeCase")
ValidatedFieldUser = _select_model_class(ValidatedFieldUserBase, None, None, None, "ValidatedFieldUser")
TypeTestModel = _select_model_class(TypeTestModelBase, None, None, None, "TypeTestModel")
ValidatedUser = _select_model_class(ValidatedUserBase, None, None, None, "ValidatedUser")
TypeAdapterTest = _select_model_class(TypeAdapterTestBase, None, None, None, "TypeAdapterTest")
MappedUser = _select_model_class(MappedUserBase, None, None, None, "MappedUser")
MappedPost = _select_model_class(MappedPostBase, None, None, None, "MappedPost")
MappedComment = _select_model_class(MappedCommentBase, None, None, None, "MappedComment")
ColumnMappingModel = _select_model_class(ColumnMappingModelBase, None, None, None, "ColumnMappingModel")
MixedAnnotationModel = _select_model_class(MixedAnnotationModelBase, None, None, None, "MixedAnnotationModel")
PydanticValidatedModel = _select_model_class(PydanticValidatedModelBase, None, None, None, "PydanticValidatedModel")
BulkUser = BulkUserBase


class BasicProviderBaseImpl(BasicProviderBase):
    def __init__(self):
        self._scenario_db_files = {}
        self._created_tables: Set[str] = set()

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def get_yes_no_adapter(self) -> "BaseSQLTypeAdapter":
        return YesOrNoBooleanAdapter()

    def get_dialect(self, scenario_name: str = "default"):
        """Return a bare, fully-constructed Firebird dialect instance.

        Used by the ``feature/basic/ddl`` subtopic (expression/dialect
        contract). Firebird rejects all three ``IF [NOT] EXISTS``
        modifiers, so the ``supports_*`` switches all report ``False``.
        """
        from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

        return FirebirdDialect()

    def _load_firebird_schema(self, filename: str) -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_firebird_test", "feature", "basic", "schema"
        )
        schema_path = os.path.join(schema_dir, filename)
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""


class BasicSyncProvider(BasicProviderBaseImpl, IBasicSyncProvider, WorkerTestProtocol):
    def __init__(self):
        super().__init__()
        self._active_backends: List = []

    def _track_backend(self, backend_instance) -> None:
        if backend_instance not in self._active_backends:
            self._active_backends.append(backend_instance)

    def _setup_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str
    ) -> Type[ActiveRecord]:
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        self._track_backend(backend)
        self._reset_table_sync(backend, table_name)
        self._created_tables.add(table_name)
        return model_class

    def _reset_table_sync(self, backend, table_name: str) -> None:
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_firebird_schema(f"{table_name}.sql")
        if schema.strip():
            backend.executescript(schema)

    def _initialize_model_schema(self, model_class: Type[ActiveRecord], table_name: str) -> None:
        self._reset_table_sync(model_class.__backend__, table_name)

    def _setup_multiple_models(
        self, model_classes: List[Tuple[Type[ActiveRecord], str]], scenario_name: str
    ) -> Tuple[Type[ActiveRecord], ...]:
        if not model_classes:
            return tuple()
        first_model_class, first_table_name = model_classes[0]
        first_model = self._setup_model(first_model_class, scenario_name, first_table_name)
        shared_backend = first_model.__backend__
        result = [first_model]
        for model_class, table_name in model_classes[1:]:
            model_class.__connection_config__ = first_model.__connection_config__
            model_class.__backend_class__ = first_model.__backend_class__
            model_class.__backend__ = shared_backend
            self._track_backend(shared_backend)
            self._initialize_model_schema(model_class, table_name)
            self._created_tables.add(table_name)
            result.append(model_class)
        return tuple(result)

    def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(User, scenario_name, "users")

    def setup_type_case_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TypeCase, scenario_name, "type_cases")

    def setup_type_test_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TypeTestModel, scenario_name, "type_tests")

    def setup_validated_field_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ValidatedFieldUser, scenario_name, "validated_field_users")

    def setup_validated_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ValidatedUser, scenario_name, "validated_users")

    def setup_pydantic_validated_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(PydanticValidatedModel, scenario_name, "pydantic_validated_models")

    def setup_mapped_models(
        self, scenario_name: str
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_multiple_models(
            [(MappedUser, "users"), (MappedPost, "posts"), (MappedComment, "comments")], scenario_name
        )

    def setup_mixed_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        return self._setup_multiple_models(
            [(ColumnMappingModel, "column_mapping_items"), (MixedAnnotationModel, "mixed_annotation_items")],
            scenario_name,
        )

    def setup_type_adapter_model_and_schema(self, scenario_name: Optional[str] = None) -> Type[ActiveRecord]:
        if scenario_name is None:
            scenario_name = self.get_test_scenarios()[0] if self.get_test_scenarios() else "default"
        return self._setup_model(TypeAdapterTest, scenario_name, "type_adapter_tests")

    def setup_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(BulkUser, scenario_name, "bulk_users")

    def setup_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(CompositeOrderItem, scenario_name, "order_items")

    def setup_order_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(OrderModel, scenario_name, "orders")

    def setup_mapped_order_item_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(MappedOrderItemModel, scenario_name, "order_items")

    def setup_product_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductModel, scenario_name, "product")

    def setup_product_form_a_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductFormAModel, scenario_name, "product")

    def setup_product_with_proxy_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductWithProxyModel, scenario_name, "product")

    def setup_product_with_column_and_adapter_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(ProductWithColumnAndAdapterModel, scenario_name, "product")

    def get_worker_connection_params(self, scenario_name: str, fixture_type: str = None) -> dict:
        from .scenarios import SCENARIO_MAP
        if scenario_name not in SCENARIO_MAP:
            if SCENARIO_MAP:
                scenario_name = next(iter(SCENARIO_MAP))
            else:
                raise ValueError("No scenarios registered")
        return {
            "backend_module": "rhosocial.activerecord.backend.impl.firebird",
            "backend_class_name": "FirebirdBackend",
            "config_class_module": "rhosocial.activerecord.backend.impl.firebird.config",
            "config_class_name": "FirebirdConnectionConfig",
            "config_kwargs": SCENARIO_MAP[scenario_name],
            "schema_sql": self.get_worker_schema_sql(scenario_name, "users"),
        }

    def get_worker_schema_sql(self, scenario_name: str, table_name: str) -> str:
        return self._load_firebird_schema(f"{table_name}.sql")

    def cleanup_after_test(self, scenario_name: str):
        for backend_instance in self._active_backends:
            try:
                for table_name in list(self._created_tables):
                    try:
                        backend_instance.execute(f"DROP TABLE {table_name}", fetch=False)
                    except Exception:
                        pass
            finally:
                try:
                    backend_instance.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
        self._created_tables.clear()
