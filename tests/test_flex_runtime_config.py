"""Tests for the Flex Consumption runtime config check (issue #345)."""

from pathlib import Path
from typing import Optional

from azure_functions_doctor.deploy_config import ResolvedField, TargetConfig
from azure_functions_doctor.handlers._helpers import RuleContext
from azure_functions_doctor.handlers.registry import (
    FLEX_CONSUMPTION_PLAN,
    HandlerRegistry,
    _evaluate_flex_runtime_config,
    _infra_declares_linux_fx_version,
)


def _target_config(
    *,
    hosting_plan: Optional[str] = None,
    runtime_name: Optional[str] = None,
    runtime_version: Optional[str] = None,
) -> TargetConfig:
    """Build a minimal :class:`TargetConfig` for handler-level tests."""
    unknown = ResolvedField(None, "unknown")
    return TargetConfig(
        hosting_plan=ResolvedField(hosting_plan, "test") if hosting_plan else unknown,
        runtime_name=ResolvedField(runtime_name, "test") if runtime_name else unknown,
        runtime_version=(ResolvedField(runtime_version, "test") if runtime_version else unknown),
        extension_version=unknown,
        deployment_storage=unknown,
        app_settings={},
    )


class TestEvaluateFlexRuntimeConfig:
    def test_non_flex_plan_skips(self) -> None:
        result = _evaluate_flex_runtime_config(
            "linux-consumption", "python", "3.12", linux_fx_present=False
        )
        assert result["status"] == "skip"
        assert "Not a Flex Consumption app" in result["detail"]

    def test_unknown_plan_skips(self) -> None:
        result = _evaluate_flex_runtime_config(None, None, None, linux_fx_present=False)
        assert result["status"] == "skip"

    def test_linux_fx_on_flex_warns(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, "python", "3.12", linux_fx_present=True
        )
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False
        assert "linuxFxVersion" in result["detail"]
        assert result["actual"] == "linuxFxVersion declared on a Flex Consumption app"

    def test_linux_fx_warn_takes_precedence_over_missing_runtime(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, None, None, linux_fx_present=True
        )
        assert result["status"] == "fail"
        assert result["severity"] == "warning"

    def test_no_runtime_declared_skips(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, None, None, linux_fx_present=False
        )
        assert result["status"] == "skip"
        assert "no functionAppConfig.runtime" in result["detail"]

    def test_partial_runtime_declared_skips(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, "python", None, linux_fx_present=False
        )
        assert result["status"] == "skip"

    def test_non_python_runtime_skips(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, "dotnet-isolated", "8.0", linux_fx_present=False
        )
        assert result["status"] == "skip"
        assert "not Python" in result["detail"]

    def test_supported_python_passes(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, "python", "3.12", linux_fx_present=False
        )
        assert result["status"] == "pass"
        assert "3.12 is supported" in result["detail"]

    def test_supported_python_314_passes(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, "python", "3.14", linux_fx_present=False
        )
        assert result["status"] == "pass"

    def test_unsupported_python_fails(self) -> None:
        result = _evaluate_flex_runtime_config(
            FLEX_CONSUMPTION_PLAN, "python", "3.9", linux_fx_present=False
        )
        assert result["status"] == "fail"
        assert result["severity"] == "error"
        assert result["gate"] is True
        assert "not supported" in result["detail"]
        assert result["actual"] == "functionAppConfig.runtime = python 3.9"


class TestInfraDeclaresLinuxFxVersion:
    def test_detects_bicep_linux_fx(self, tmp_path: Path) -> None:
        (tmp_path / "main.bicep").write_text(
            "resource site 'x' = { properties: { linuxFxVersion: 'Python|3.12' } }",
            encoding="utf-8",
        )
        assert _infra_declares_linux_fx_version(tmp_path) is True

    def test_detects_json_linux_fx_case_insensitive(self, tmp_path: Path) -> None:
        (tmp_path / "azuredeploy.json").write_text(
            '{"properties": {"siteConfig": {"LinuxFxVersion": "Python|3.12"}}}',
            encoding="utf-8",
        )
        assert _infra_declares_linux_fx_version(tmp_path) is True

    def test_ignores_local_settings(self, tmp_path: Path) -> None:
        (tmp_path / "local.settings.json").write_text(
            '{"Values": {"linuxFxVersion": "Python|3.12"}}', encoding="utf-8"
        )
        assert _infra_declares_linux_fx_version(tmp_path) is False

    def test_no_infra_returns_false(self, tmp_path: Path) -> None:
        assert _infra_declares_linux_fx_version(tmp_path) is False

    def test_skips_unreadable_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "broken.bicep"
        bad.write_text("no runtime keyword here", encoding="utf-8")
        assert _infra_declares_linux_fx_version(tmp_path) is False


class TestFlexHandlerWiring:
    def _run(self, context: Optional[RuleContext], path: Path) -> dict[str, object]:
        registry = HandlerRegistry()
        return dict(registry._handle_flex_runtime_config({}, path, context))

    def test_handler_without_context_skips(self, tmp_path: Path) -> None:
        result = self._run(None, tmp_path)
        assert result["status"] == "skip"

    def test_handler_flex_supported_python_passes(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(
                hosting_plan=FLEX_CONSUMPTION_PLAN,
                runtime_name="python",
                runtime_version="3.12",
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"

    def test_handler_flex_with_linux_fx_warns(self, tmp_path: Path) -> None:
        (tmp_path / "main.bicep").write_text(
            "properties: { linuxFxVersion: 'Python|3.12' }", encoding="utf-8"
        )
        context: RuleContext = {
            "target_config": _target_config(
                hosting_plan=FLEX_CONSUMPTION_PLAN,
                runtime_name="python",
                runtime_version="3.12",
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"

    def test_handler_non_flex_skips(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="premium"),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "skip"


class TestLinuxFxVersionScoping:
    """check_linux_fx_version should defer to the Flex check for Flex apps."""

    def _run(self, context: Optional[RuleContext], path: Path) -> dict[str, object]:
        registry = HandlerRegistry()
        return dict(registry._handle_linux_fx_version({}, path, context))

    def test_flex_app_skips_linux_fx_check(self, tmp_path: Path) -> None:
        (tmp_path / "main.bicep").write_text(
            "properties: { linuxFxVersion: 'Python|3.12' }", encoding="utf-8"
        )
        context: RuleContext = {
            "target_config": _target_config(hosting_plan=FLEX_CONSUMPTION_PLAN),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "skip"
        assert "check_flex_runtime_config" in str(result["detail"])

    def test_non_flex_app_still_validates_linux_fx(self, tmp_path: Path) -> None:
        (tmp_path / "main.bicep").write_text(
            "properties: { linuxFxVersion: 'Python|3.9' }", encoding="utf-8"
        )
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="linux-consumption"),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"

    def test_no_context_still_validates_linux_fx(self, tmp_path: Path) -> None:
        (tmp_path / "main.bicep").write_text(
            "properties: { linuxFxVersion: 'Python|3.12' }", encoding="utf-8"
        )
        result = self._run(None, tmp_path)
        assert result["status"] == "pass"
