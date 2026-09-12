"""Tests for the Flex-aware FUNCTIONS_EXTENSION_VERSION check (issue #346)."""

import json
from pathlib import Path
from typing import Optional

from azure_functions_doctor.deploy_config import ResolvedField, TargetConfig
from azure_functions_doctor.handlers._helpers import RuleContext
from azure_functions_doctor.handlers.registry import (
    FLEX_CONSUMPTION_PLAN,
    HandlerRegistry,
    _evaluate_flex_extension_version,
)


def _target_config(
    *,
    hosting_plan: Optional[str] = None,
    extension_version: Optional[str] = None,
) -> TargetConfig:
    unknown = ResolvedField(None, "unknown")
    return TargetConfig(
        hosting_plan=ResolvedField(hosting_plan, "test") if hosting_plan else unknown,
        runtime_name=unknown,
        runtime_version=unknown,
        extension_version=(
            ResolvedField(extension_version, "test") if extension_version else unknown
        ),
        deployment_storage=unknown,
        app_settings={},
    )


def _write_local_settings(path: Path, ext: Optional[str]) -> None:
    values = {} if ext is None else {"FUNCTIONS_EXTENSION_VERSION": ext}
    (path / "local.settings.json").write_text(json.dumps({"Values": values}), encoding="utf-8")


class TestEvaluateFlexExtensionVersion:
    def test_missing_skips(self) -> None:
        result = _evaluate_flex_extension_version(None)
        assert result["status"] == "skip"
        assert "not required on Flex Consumption" in result["detail"]

    def test_present_warns(self) -> None:
        result = _evaluate_flex_extension_version("~4")
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False
        assert "not supported" in result["detail"]
        assert result["actual"] == "FUNCTIONS_EXTENSION_VERSION = ~4"


class TestHandlerFlexAware:
    def _run(self, context: Optional[RuleContext], path: Path) -> dict[str, object]:
        registry = HandlerRegistry()
        return dict(registry._handle_functions_extension_version({}, path, context))

    def test_flex_missing_skips(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(hosting_plan=FLEX_CONSUMPTION_PLAN),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "skip"
        assert "Flex Consumption" in str(result["detail"])

    def test_flex_present_warns(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(
                hosting_plan=FLEX_CONSUMPTION_PLAN, extension_version="~4"
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"

    def test_non_flex_missing_still_fails(self, tmp_path: Path) -> None:
        _write_local_settings(tmp_path, None)
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="linux-consumption"),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"
        assert "not set" in str(result["detail"])

    def test_non_flex_v4_passes(self, tmp_path: Path) -> None:
        _write_local_settings(tmp_path, "~4")
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="premium"),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"

    def test_non_flex_legacy_fails(self, tmp_path: Path) -> None:
        _write_local_settings(tmp_path, "~3")
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="linux-consumption"),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"
        assert "Legacy runtimes" in str(result["detail"])

    def test_no_context_keeps_legacy_behavior(self, tmp_path: Path) -> None:
        # No target_config: not treated as Flex, existing local.settings logic runs.
        _write_local_settings(tmp_path, "~4")
        result = self._run(None, tmp_path)
        assert result["status"] == "pass"

    def test_no_context_missing_settings_skips(self, tmp_path: Path) -> None:
        result = self._run(None, tmp_path)
        assert result["status"] == "skip"
        assert "not present" in str(result["detail"])
