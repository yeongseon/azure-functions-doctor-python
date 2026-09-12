"""Tests for the Flex Consumption deployment storage configuration check (issue #351)."""

import json
from pathlib import Path
from typing import Optional

from azure_functions_doctor.deploy_config import (
    ResolvedField,
    TargetConfig,
    flex_deployment_storage_shape,
)
from azure_functions_doctor.handlers._helpers import RuleContext
from azure_functions_doctor.handlers.registry import (
    FLEX_CONSUMPTION_PLAN,
    HandlerRegistry,
    _evaluate_flex_deployment_storage,
)


def _target_config(*, hosting_plan: Optional[str] = None) -> TargetConfig:
    unknown = ResolvedField(None, "unknown")
    return TargetConfig(
        hosting_plan=ResolvedField(hosting_plan, "test") if hosting_plan else unknown,
        runtime_name=unknown,
        runtime_version=unknown,
        extension_version=unknown,
        deployment_storage=unknown,
        app_settings={},
    )


def _write_infra(tmp_path: Path, storage: object) -> None:
    doc = {
        "resources": [
            {
                "properties": {
                    "functionAppConfig": {
                        "deployment": {"storage": storage},
                    }
                }
            }
        ]
    }
    (tmp_path / "main.json").write_text(json.dumps(doc), encoding="utf-8")


class TestEvaluateFlexDeploymentStorage:
    def test_non_flex_skips(self) -> None:
        result = _evaluate_flex_deployment_storage("linux-consumption", None)
        assert result["status"] == "skip"
        assert "Not a Flex Consumption app" in result["detail"]

    def test_none_plan_skips(self) -> None:
        result = _evaluate_flex_deployment_storage(None, {"value": "x"})
        assert result["status"] == "skip"

    def test_flex_no_storage_block_skips(self) -> None:
        result = _evaluate_flex_deployment_storage(FLEX_CONSUMPTION_PLAN, None)
        assert result["status"] == "skip"
        assert "no functionAppConfig.deployment.storage" in result["detail"]

    def test_well_formed_managed_identity_passes(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {
                "type": "blobContainer",
                "value": "https://acct.blob.core.windows.net/app",
                "authentication": {
                    "type": "SystemAssignedIdentity",
                },
            },
        )
        assert result["status"] == "pass"
        assert "configured" in result["detail"]

    def test_well_formed_connection_string_passes(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {
                "value": "https://acct.blob.core.windows.net/app",
                "authentication": {
                    "type": "StorageAccountConnectionString",
                    "storageAccountConnectionStringName": "DEPLOYMENT_STORAGE",
                },
            },
        )
        assert result["status"] == "pass"

    def test_missing_container_warns(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {"authentication": {"type": "SystemAssignedIdentity"}},
        )
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False
        assert "no deployment container" in result["detail"]

    def test_empty_container_warns(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {"value": "   ", "authentication": {"type": "SystemAssignedIdentity"}},
        )
        assert result["status"] == "fail"
        assert "no deployment container" in result["detail"]

    def test_missing_authentication_warns(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {"value": "https://acct.blob.core.windows.net/app"},
        )
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert "no authentication is configured" in result["detail"]

    def test_authentication_missing_type_warns(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {
                "value": "https://acct.blob.core.windows.net/app",
                "authentication": {},
            },
        )
        assert result["status"] == "fail"
        assert "missing a 'type'" in result["detail"]

    def test_connection_string_missing_name_warns(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {
                "value": "https://acct.blob.core.windows.net/app",
                "authentication": {"type": "StorageAccountConnectionString"},
            },
        )
        assert result["status"] == "fail"
        assert "storageAccountConnectionStringName" in result["detail"]
        assert result["actual"]

    def test_multiple_problems_reported(self) -> None:
        result = _evaluate_flex_deployment_storage(
            FLEX_CONSUMPTION_PLAN,
            {"authentication": "not-a-dict"},
        )
        assert result["status"] == "fail"
        assert "no deployment container" in result["detail"]
        assert "no authentication is configured" in result["detail"]


class TestFlexDeploymentStorageShape:
    def test_reads_storage_from_infra_json(self, tmp_path: Path) -> None:
        storage = {"value": "https://acct.blob.core.windows.net/app"}
        _write_infra(tmp_path, storage)
        result = flex_deployment_storage_shape(tmp_path)
        assert result == storage

    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        (tmp_path / "main.json").write_text(json.dumps({"resources": []}), encoding="utf-8")
        assert flex_deployment_storage_shape(tmp_path) is None

    def test_bicep_only_project_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "main.bicep").write_text(
            "resource fa 'Microsoft.Web/sites@2023-01-01' = {}", encoding="utf-8"
        )
        assert flex_deployment_storage_shape(tmp_path) is None

    def test_invalid_json_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "main.json").write_text("{not valid", encoding="utf-8")
        assert flex_deployment_storage_shape(tmp_path) is None


class TestHandler:
    def _run(self, context: Optional[RuleContext], path: Path) -> dict[str, object]:
        registry = HandlerRegistry()
        return dict(registry._handle_flex_deployment_storage({}, path, context))

    def test_no_context_skips(self, tmp_path: Path) -> None:
        result = self._run(None, tmp_path)
        assert result["status"] == "skip"
        assert "could not be resolved" in str(result["detail"])

    def test_non_flex_skips(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="linux-consumption"),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "skip"

    def test_flex_reads_infra_and_warns(self, tmp_path: Path) -> None:
        _write_infra(tmp_path, {"value": "https://acct.blob.core.windows.net/app"})
        context: RuleContext = {
            "target_config": _target_config(hosting_plan=FLEX_CONSUMPTION_PLAN),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert "no authentication is configured" in str(result["detail"])

    def test_flex_well_formed_passes(self, tmp_path: Path) -> None:
        _write_infra(
            tmp_path,
            {
                "value": "https://acct.blob.core.windows.net/app",
                "authentication": {"type": "SystemAssignedIdentity"},
            },
        )
        context: RuleContext = {
            "target_config": _target_config(hosting_plan=FLEX_CONSUMPTION_PLAN),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"

    def test_flex_no_infra_skips(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(hosting_plan=FLEX_CONSUMPTION_PLAN),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "skip"
