import os
import sys
import logging
from typing import Type, List, Tuple, Optional, Any

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
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    AsyncPydanticValidatedModel as AsyncPydanticValidatedModelBase,
)
from rhosocial.activerecord.testsuite.feature.basic.fixtures.models import (
    BulkUser as BulkUserBase, AsyncBulkUser as AsyncBulkUserBase
)

from rhosocial.activerecord.testsuite.feature.basic.interfaces import IBasicProvider
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
AsyncPydanticValidatedModel = _select_model_class(AsyncPydanticValidatedModelBase, None, None, None, "AsyncPydanticValidatedModel")
BulkUser = BulkUserBase
AsyncBulkUser = AsyncBulkUserBase


class BasicProvider(IBasicProvider, WorkerTestProtocol):
    def __init__(self):
        self._active_backends = []

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _track_backend(self, backend):
        if backend not in self._active_backends:
            self._active_backends.append(backend)

    def _setup_model(self, model_class, scenario_name, table_name):
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        self._track_backend(backend)
        self._reset_table(backend, table_name)
        return model_class

    def _reset_table(self, backend, table_name):
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_schema(f"{table_name}.sql")
        if schema.strip():
            backend.executescript(schema)

    def _load_schema(self, filename):
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial",
                                  "activerecord_firebird_test", "feature", "basic", "schema")
        path = os.path.join(schema_dir, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
        return ""

    def _setup_multiple_models(self, models, scenario_name):
        if not models:
            return tuple()
        first_cls, first_tbl = models[0]
        first = self._setup_model(first_cls, scenario_name, first_tbl)
        shared = first.__backend__
        result = [first]
        for cls, tbl in models[1:]:
            cls.__connection_config__ = first.__connection_config__
            cls.__backend_class__ = first.__backend_class__
            cls.__backend__ = shared
            self._reset_table(shared, tbl)
            result.append(cls)
        return tuple(result)

    def setup_user_model(self, scenario_name):
        return self._setup_model(User, scenario_name, "users")

    def setup_type_case_model(self, scenario_name):
        return self._setup_model(TypeCase, scenario_name, "type_cases")

    def setup_type_test_model(self, scenario_name):
        return self._setup_model(TypeTestModel, scenario_name, "type_tests")

    def setup_validated_field_user_model(self, scenario_name):
        return self._setup_model(ValidatedFieldUser, scenario_name, "validated_field_users")

    def setup_validated_user_model(self, scenario_name):
        return self._setup_model(ValidatedUser, scenario_name, "validated_users")

    def setup_pydantic_validated_model(self, scenario_name):
        return self._setup_model(PydanticValidatedModel, scenario_name, "pydantic_validated_models")

    async def setup_async_pydantic_validated_model(self, scenario_name: str):
        raise NotImplementedError("Firebird backend does not support async")

    def setup_mapped_models(self, scenario_name):
        return self._setup_multiple_models([
            (MappedUser, "users"), (MappedPost, "posts"), (MappedComment, "comments")
        ], scenario_name)

    def setup_mixed_models(self, scenario_name):
        return self._setup_multiple_models([
            (ColumnMappingModel, "column_mapping_items"),
            (MixedAnnotationModel, "mixed_annotation_items")
        ], scenario_name)

    def setup_type_adapter_model_and_schema(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(TypeAdapterTest, scenario_name, "type_adapter_tests")

    def setup_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        """Sets up the database for the `BulkUser` model tests."""
        return self._setup_model(BulkUser, scenario_name, "bulk_users")

    async def setup_async_bulk_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        """Sets up the database for the `AsyncBulkUser` model tests."""
        return await self._setup_async_model(AsyncBulkUser, scenario_name, "bulk_users")

    def get_yes_no_adapter(self):
        return YesOrNoBooleanAdapter()

    async def setup_async_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_type_case_model(self, scenario_name: str) -> Type[ActiveRecord]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_type_test_model(self, scenario_name: str) -> Type[ActiveRecord]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_validated_field_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_validated_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_mapped_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_mixed_models(self, scenario_name: str) -> Tuple[Type[ActiveRecord], ...]:
        raise NotImplementedError("Firebird backend does not support async")

    async def setup_async_type_adapter_model_and_schema(self, scenario_name: str) -> Type[ActiveRecord]:
        raise NotImplementedError("Firebird backend does not support async")

    async def cleanup_after_test_async(self, scenario_name: str):
        raise NotImplementedError("Firebird backend does not support async")

    def cleanup_after_test(self, scenario_name):
        tables = ["users", "type_cases", "type_tests", "validated_field_users",
                  "validated_users", "type_adapter_tests", "posts", "comments",
                  "column_mapping_items", "mixed_annotation_items",
                  "pydantic_validated_models"]
        for b in self._active_backends:
            try:
                for t in tables:
                    try:
                        b.execute(f"DROP TABLE {t}", fetch=False)
                    except Exception:
                        pass
            finally:
                try:
                    b.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()

    def get_worker_connection_params(self, scenario_name, fixture_type=None):
        from .scenarios import SCENARIO_MAP
        name = scenario_name if scenario_name in SCENARIO_MAP else next(iter(SCENARIO_MAP))
        return {
            'backend_module': 'rhosocial.activerecord.backend.impl.firebird',
            'backend_class_name': 'FirebirdBackend',
            'config_class_module': 'rhosocial.activerecord.backend.impl.firebird.config',
            'config_class_name': 'FirebirdConnectionConfig',
            'config_kwargs': SCENARIO_MAP[name],
            'schema_sql': "",
        }

    def get_worker_schema_sql(self, scenario_name, table_name):
        return self._load_schema(f"{table_name}.sql")
