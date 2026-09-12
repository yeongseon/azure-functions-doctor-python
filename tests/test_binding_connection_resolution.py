"""Tests for the binding-to-connection resolution check (issue #352)."""

import json
from pathlib import Path
from typing import Optional

from azure_functions_doctor.deploy_config import (
    ResolvedField,
    TargetConfig,
    local_settings_values,
)
from azure_functions_doctor.handlers._helpers import (
    RuleContext,
    _collect_binding_connections,
)
from azure_functions_doctor.handlers.registry import (
    FLEX_CONSUMPTION_PLAN,
    HandlerRegistry,
    _evaluate_binding_connection_resolution,
)

SAMPLE_APP = """\
import azure.functions as func

app = func.FunctionApp()


@app.service_bus_queue_trigger(arg_name="msg", queue_name="q", connection="ServiceBusConnection")
def handle_bus(msg: func.ServiceBusMessage) -> None:
    pass


@app.blob_trigger(arg_name="blob", path="c/{name}", connection="StorageConnection")
def handle_blob(blob: func.InputStream) -> None:
    pass
"""


def _target_config(*, app_settings: Optional[dict[str, str]] = None) -> TargetConfig:
    unknown = ResolvedField(None, "unknown")
    return TargetConfig(
        hosting_plan=unknown,
        runtime_name=unknown,
        runtime_version=unknown,
        extension_version=unknown,
        deployment_storage=unknown,
        app_settings=app_settings or {},
    )


def _write_local_settings(tmp_path: Path, values: dict[str, str]) -> None:
    (tmp_path / "local.settings.json").write_text(
        json.dumps({"IsEncrypted": False, "Values": values}), encoding="utf-8"
    )


class TestCollectBindingConnections:
    def test_collects_string_literal_connections(self, tmp_path: Path) -> None:
        (tmp_path / "function_app.py").write_text(SAMPLE_APP, encoding="utf-8")
        refs = _collect_binding_connections(tmp_path)
        names = sorted(name for name, _label, _ln in refs)
        assert names == ["ServiceBusConnection", "StorageConnection"]
        labels = {label for _name, label, _ln in refs}
        assert any("function_app.py:handle_bus" in label for label in labels)

    def test_ignores_non_literal_connection(self, tmp_path: Path) -> None:
        src = (
            "import azure.functions as func\n"
            "import os\n"
            "app = func.FunctionApp()\n\n"
            "@app.blob_trigger(arg_name='b', path='c/{n}', "
            "connection=os.environ['X'])\n"
            "def h(b):\n    pass\n"
        )
        (tmp_path / "function_app.py").write_text(src, encoding="utf-8")
        assert _collect_binding_connections(tmp_path) == []

    def test_ignores_decorators_on_unknown_alias(self, tmp_path: Path) -> None:
        src = (
            "import azure.functions as func\n"
            "other = something()\n\n"
            "@other.blob_trigger(connection='StorageConnection')\n"
            "def h(b):\n    pass\n"
        )
        (tmp_path / "function_app.py").write_text(src, encoding="utf-8")
        assert _collect_binding_connections(tmp_path) == []

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "broken.py").write_text("def (:", encoding="utf-8")
        assert _collect_binding_connections(tmp_path) == []

    def test_blueprint_alias_supported(self, tmp_path: Path) -> None:
        src = (
            "import azure.functions as func\n"
            "bp = func.Blueprint()\n\n"
            "@bp.queue_trigger(arg_name='m', queue_name='q', "
            "connection='QueueConnection')\n"
            "def h(m):\n    pass\n"
        )
        (tmp_path / "bp.py").write_text(src, encoding="utf-8")
        refs = _collect_binding_connections(tmp_path)
        assert [name for name, _l, _n in refs] == ["QueueConnection"]


class TestLocalSettingsValues:
    def test_returns_string_values(self, tmp_path: Path) -> None:
        _write_local_settings(tmp_path, {"A": "1", "B": "2"})
        assert local_settings_values(tmp_path) == {"A": "1", "B": "2"}

    def test_absent_file_returns_empty(self, tmp_path: Path) -> None:
        assert local_settings_values(tmp_path) == {}

    def test_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "local.settings.json").write_text("{bad", encoding="utf-8")
        assert local_settings_values(tmp_path) == {}

    def test_non_string_values_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "local.settings.json").write_text(
            json.dumps({"Values": {"A": "x", "B": 5, "C": True}}), encoding="utf-8"
        )
        assert local_settings_values(tmp_path) == {"A": "x"}

    def test_missing_values_key_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "local.settings.json").write_text(
            json.dumps({"IsEncrypted": False}), encoding="utf-8"
        )
        assert local_settings_values(tmp_path) == {}


class TestEvaluateBindingConnectionResolution:
    def test_no_references_passes(self) -> None:
        result = _evaluate_binding_connection_resolution([], {"A": "1"})
        assert result["status"] == "pass"
        assert "No named binding connections" in result["detail"]

    def test_all_resolved_passes(self) -> None:
        refs = [("StorageConnection", "app.py:h")]
        result = _evaluate_binding_connection_resolution(
            refs, {"StorageConnection": "DefaultEndpointsProtocol=..."}
        )
        assert result["status"] == "pass"

    def test_unresolved_warns(self) -> None:
        refs = [("ServiceBusConnection", "app.py:h")]
        result = _evaluate_binding_connection_resolution(refs, {})
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False
        assert "ServiceBusConnection" in result["detail"]
        assert result["actual"] == "Unresolved connections: ServiceBusConnection"

    def test_identity_group_suffix_resolves(self) -> None:
        refs = [("MyConn", "app.py:h")]
        result = _evaluate_binding_connection_resolution(
            refs, {"MyConn__serviceUri": "https://x.servicebus.windows.net"}
        )
        assert result["status"] == "pass"

    def test_identity_group_account_name_resolves(self) -> None:
        refs = [("MyConn", "app.py:h")]
        result = _evaluate_binding_connection_resolution(refs, {"MyConn__accountName": "acct"})
        assert result["status"] == "pass"

    def test_mixed_resolved_and_unresolved(self) -> None:
        refs = [
            ("Configured", "app.py:a"),
            ("Missing", "app.py:b"),
        ]
        result = _evaluate_binding_connection_resolution(refs, {"Configured": "x"})
        assert result["status"] == "fail"
        assert "Missing" in result["detail"]
        assert "Configured" not in result["actual"]

    def test_duplicate_references_deduplicated(self) -> None:
        refs = [
            ("Missing", "app.py:a"),
            ("Missing", "app.py:a"),
        ]
        result = _evaluate_binding_connection_resolution(refs, {})
        assert result["detail"].count("app.py:a") == 1

    def test_actual_lists_unique_sorted_names(self) -> None:
        refs = [
            ("Zeta", "app.py:a"),
            ("Alpha", "app.py:b"),
            ("Zeta", "app.py:c"),
        ]
        result = _evaluate_binding_connection_resolution(refs, {})
        assert result["actual"] == "Unresolved connections: Alpha, Zeta"


class TestHandler:
    def _run(self, context: Optional[RuleContext], path: Path) -> dict[str, object]:
        registry = HandlerRegistry()
        return dict(registry._handle_binding_connection_resolution({}, path, context))

    def test_no_references_passes(self, tmp_path: Path) -> None:
        (tmp_path / "function_app.py").write_text(
            "import azure.functions as func\napp = func.FunctionApp()\n",
            encoding="utf-8",
        )
        result = self._run(None, tmp_path)
        assert result["status"] == "pass"

    def test_resolves_from_local_settings(self, tmp_path: Path) -> None:
        (tmp_path / "function_app.py").write_text(SAMPLE_APP, encoding="utf-8")
        _write_local_settings(
            tmp_path,
            {"ServiceBusConnection": "Endpoint=...", "StorageConnection": "x"},
        )
        result = self._run(None, tmp_path)
        assert result["status"] == "pass"

    def test_resolves_from_target_config(self, tmp_path: Path) -> None:
        (tmp_path / "function_app.py").write_text(SAMPLE_APP, encoding="utf-8")
        context: RuleContext = {
            "target_config": _target_config(
                app_settings={
                    "ServiceBusConnection": "x",
                    "StorageConnection": "y",
                }
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"

    def test_unresolved_warns(self, tmp_path: Path) -> None:
        (tmp_path / "function_app.py").write_text(SAMPLE_APP, encoding="utf-8")
        result = self._run(None, tmp_path)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert "ServiceBusConnection" in str(result["detail"])
        assert "StorageConnection" in str(result["detail"])

    def test_identity_group_in_target_config_resolves(self, tmp_path: Path) -> None:
        src = (
            "import azure.functions as func\n"
            "app = func.FunctionApp()\n\n"
            "@app.service_bus_queue_trigger(arg_name='m', queue_name='q', "
            "connection='SbConn')\n"
            "def h(m):\n    pass\n"
        )
        (tmp_path / "function_app.py").write_text(src, encoding="utf-8")
        context: RuleContext = {
            "target_config": _target_config(
                app_settings={"SbConn__fullyQualifiedNamespace": "x.servicebus"}
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"

    def test_hosting_plan_field_unused_but_context_ok(self, tmp_path: Path) -> None:
        # A Flex target config with the setting present still resolves cleanly.
        (tmp_path / "function_app.py").write_text(SAMPLE_APP, encoding="utf-8")
        tc = TargetConfig(
            hosting_plan=ResolvedField(FLEX_CONSUMPTION_PLAN, "test"),
            runtime_name=ResolvedField(None, "unknown"),
            runtime_version=ResolvedField(None, "unknown"),
            extension_version=ResolvedField(None, "unknown"),
            deployment_storage=ResolvedField(None, "unknown"),
            app_settings={"ServiceBusConnection": "x", "StorageConnection": "y"},
        )
        context: RuleContext = {"target_config": tc}
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"
