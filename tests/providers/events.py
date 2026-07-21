# tests/providers/events.py
import os
import logging
from typing import Type, List, Set

from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.testsuite.utils import select_fixture
from rhosocial.activerecord.testsuite.feature.events.fixtures.models import (
    EventTestModel as EventTestModelBase,
    EventTrackingModel as EventTrackingModelBase,
)
from rhosocial.activerecord.testsuite.feature.events.interfaces import (
    EventsProviderBase,
    IEventsSyncProvider,
)
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


EventTestModel = _select_model_class(EventTestModelBase, None, None, None, "EventTestModel")
EventTrackingModel = _select_model_class(EventTrackingModelBase, None, None, None, "EventTrackingModel")


class EventsProviderBaseImpl(EventsProviderBase):
    def __init__(self):
        self._created_tables: Set[str] = set()

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _load_firebird_schema(self, filename: str) -> str:
        schema_dir = os.path.join(
            os.path.dirname(__file__), "..", "rhosocial", "activerecord_firebird_test", "feature", "events", "schema"
        )
        schema_path = os.path.join(schema_dir, filename)
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""


class EventsSyncProvider(EventsProviderBaseImpl, IEventsSyncProvider):
    def __init__(self):
        super().__init__()
        self._active_backends: List = []

    def _setup_model(
        self, model_class: Type[ActiveRecord], scenario_name: str, table_name: str
    ) -> Type[ActiveRecord]:
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        if backend not in self._active_backends:
            self._active_backends.append(backend)
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_firebird_schema(f"{table_name}.sql")
        if schema.strip():
            backend.executescript(schema)
        self._created_tables.add(table_name)
        return model_class

    def setup_event_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(EventTestModel, scenario_name, "event_tests")

    def setup_event_tracking_model(self, scenario_name: str) -> Type[ActiveRecord]:
        return self._setup_model(EventTrackingModel, scenario_name, "event_tracking_models")

    def cleanup_after_test(self, scenario_name: str):
        for backend in self._active_backends:
            try:
                for table_name in list(self._created_tables):
                    try:
                        backend.execute(f"DROP TABLE {table_name}", fetch=False)
                    except Exception:
                        pass
            finally:
                try:
                    backend.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
        self._created_tables.clear()
