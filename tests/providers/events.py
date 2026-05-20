import os
import sys
import logging
from typing import Type, List

from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.testsuite.utils import select_fixture
from rhosocial.activerecord.testsuite.feature.events.fixtures.models import (
    EventTestModel as EventTestModelBase,
    EventTrackingModel as EventTrackingModelBase,
)
from rhosocial.activerecord.testsuite.feature.events.interfaces import IEventsProvider
from .scenarios import get_enabled_scenarios, get_scenario

logger = logging.getLogger(__name__)


def _select_model_class(base_cls, py312_cls, py311_cls, py310_cls, name):
    candidates = [c for c in [py312_cls, py311_cls, py310_cls, base_cls] if c is not None]
    return select_fixture(*candidates)


EventTestModel = _select_model_class(EventTestModelBase, None, None, None, "EventTestModel")
EventTrackingModel = _select_model_class(EventTrackingModelBase, None, None, None, "EventTrackingModel")


class EventsProvider(IEventsProvider):
    def __init__(self):
        self._active_backends = []

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _setup_model(self, model_class, scenario_name, table_name):
        backend_class, config = get_scenario(scenario_name)
        model_class.configure(config, backend_class)
        backend = model_class.__backend__
        if backend not in self._active_backends:
            self._active_backends.append(backend)
        try:
            backend.execute(f"DROP TABLE {table_name}", fetch=False)
        except Exception:
            pass
        schema = self._load_schema(f"{table_name}.sql")
        if schema.strip():
            backend.executescript(schema)
        return model_class

    def _load_schema(self, filename):
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "rhosocial",
                                  "activerecord_firebird_test", "feature", "events", "schema")
        path = os.path.join(schema_dir, filename)
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return ""

    def setup_event_model(self, scenario_name):
        return self._setup_model(EventTestModel, scenario_name, "event_tests")

    def setup_event_tracking_model(self, scenario_name):
        return self._setup_model(EventTrackingModel, scenario_name, "event_tracking_models")

    def cleanup_after_test(self, scenario_name):
        for b in self._active_backends:
            try:
                for t in ["event_tests", "event_tracking_models"]:
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
