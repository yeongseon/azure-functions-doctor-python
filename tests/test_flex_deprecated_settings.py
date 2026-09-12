"""Tests for the Flex Consumption deprecated app settings check (issue #350)."""

from pathlib import Path
from typing import Optional

from azure_functions_doctor.compatibility import Catalog, load_catalog
from azure_functions_doctor.deploy_config import ResolvedField, TargetConfig
from azure_functions_doctor.handlers._helpers import RuleContext
from azure_functions_doctor.handlers.registry import (
    FLEX_CONSUMPTION_PLAN,
    FLEX_DEPRECATED_APP_SETTINGS,
    HandlerRegistry,
    _evaluate_flex_deprecated_settings,
)


def _target_config(
    *,
    hosting_plan: Optional[str] = None,
    app_settings: Optional[dict[str, str]] = None,
) -> TargetConfig:
    unknown = ResolvedField(None, "unknown")
    return TargetConfig(
        hosting_plan=ResolvedField(hosting_plan, "test") if hosting_plan else unknown,
        runtime_name=unknown,
        runtime_version=unknown,
        extension_version=unknown,
        deployment_storage=unknown,
        app_settings=app_settings or {},
    )


class TestCatalogFact:
    def test_flex_deprecated_settings_fact_present(self) -> None:
        fact = load_catalog().flex_deprecated_settings_fact()
        assert fact is not None
        assert fact.fact_id == "flex-deprecated-app-settings"
        assert fact.applies_to.get("hosting_plan") == FLEX_CONSUMPTION_PLAN
        assert fact.source_url.startswith("https://learn.microsoft.com/")

    def test_deprecated_map_excludes_owned_settings(self) -> None:
        # LinuxFxVersion is owned by #345 and FUNCTIONS_EXTENSION_VERSION by #346;
        # neither may appear in this rule's map to avoid duplicate findings.
        assert "LinuxFxVersion" not in FLEX_DEPRECATED_APP_SETTINGS
        assert "FUNCTIONS_EXTENSION_VERSION" not in FLEX_DEPRECATED_APP_SETTINGS


class TestEvaluateFlexDeprecatedSettings:
    def test_non_flex_skips(self) -> None:
        result = _evaluate_flex_deprecated_settings(
            "linux-consumption", {"FUNCTIONS_WORKER_RUNTIME": "python"}
        )
        assert result["status"] == "skip"
        assert "Not a Flex Consumption app" in result["detail"]

    def test_none_plan_skips(self) -> None:
        result = _evaluate_flex_deprecated_settings(None, {})
        assert result["status"] == "skip"

    def test_flex_clean_passes(self) -> None:
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN, {"APPLICATIONINSIGHTS_CONNECTION_STRING": "x"}
        )
        assert result["status"] == "pass"
        assert "No deprecated" in result["detail"]

    def test_flex_deprecated_warns_with_remediation(self) -> None:
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN,
            {
                "FUNCTIONS_WORKER_RUNTIME": "python",
                "WEBSITE_RUN_FROM_PACKAGE": "1",
            },
        )
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False
        assert "FUNCTIONS_WORKER_RUNTIME" in result["detail"]
        assert "WEBSITE_RUN_FROM_PACKAGE" in result["detail"]
        # Per-setting remediation text is included.
        assert "functionAppConfig.runtime" in result["detail"]
        assert result["actual"] == (
            "Deprecated app settings declared: FUNCTIONS_WORKER_RUNTIME, WEBSITE_RUN_FROM_PACKAGE"
        )
        # Catalog evidence is attached.
        assert result["source_url"].startswith("https://learn.microsoft.com/")
        assert result["catalog_version"]
        assert result["last_verified"]

    def test_reports_in_catalog_map_order(self) -> None:
        # Declared out of order, reported in FLEX_DEPRECATED_APP_SETTINGS order.
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN,
            {
                "WEBSITE_VNET_ROUTE_ALL": "1",
                "FUNCTIONS_WORKER_RUNTIME": "python",
            },
        )
        assert result["actual"] == (
            "Deprecated app settings declared: FUNCTIONS_WORKER_RUNTIME, WEBSITE_VNET_ROUTE_ALL"
        )

    def test_linux_fx_version_not_reported(self) -> None:
        # De-duplication: LinuxFxVersion is owned by #345 and must never be
        # emitted here even if present as an app setting on a Flex app.
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN,
            {"LinuxFxVersion": "Python|3.11", "linuxFxVersion": "Python|3.11"},
        )
        assert result["status"] == "pass"
        assert "LinuxFxVersion" not in result["detail"]

    def test_extension_version_not_reported(self) -> None:
        # De-duplication: FUNCTIONS_EXTENSION_VERSION is owned by #346.
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN, {"FUNCTIONS_EXTENSION_VERSION": "~4"}
        )
        assert result["status"] == "pass"

    def test_all_documented_settings_detected(self) -> None:
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN,
            {name: "x" for name in FLEX_DEPRECATED_APP_SETTINGS},
        )
        assert result["status"] == "fail"
        for name in FLEX_DEPRECATED_APP_SETTINGS:
            assert name in result["detail"]

    def test_explicit_catalog_argument_is_used(self) -> None:
        catalog = load_catalog()
        fact = catalog.flex_deprecated_settings_fact()
        assert fact is not None
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN,
            {"ENABLE_ORYX_BUILD": "true"},
            catalog=catalog,
        )
        assert result["status"] == "fail"
        assert result["source_url"] == fact.source_url

    def test_missing_catalog_fact_falls_back(self) -> None:
        # Defensive path: if the catalog has no flex_deprecated_settings fact,
        # the finding still reports expected/actual without catalog evidence.
        empty = Catalog(
            catalog_version="0.0.0",
            last_verified="2026-09-06",
            sources={},
            facts=(),
        )
        result = _evaluate_flex_deprecated_settings(
            FLEX_CONSUMPTION_PLAN,
            {"ENABLE_ORYX_BUILD": "true"},
            catalog=empty,
        )
        assert result["status"] == "fail"
        assert result["expected"] == "No deprecated legacy app settings on Flex Consumption"
        assert "source_url" not in result


class TestHandler:
    def _run(self, context: Optional[RuleContext], path: Path) -> dict[str, object]:
        registry = HandlerRegistry()
        return dict(registry._handle_flex_deprecated_settings({}, path, context))

    def test_no_context_skips(self, tmp_path: Path) -> None:
        result = self._run(None, tmp_path)
        assert result["status"] == "skip"
        assert "could not be resolved" in str(result["detail"])

    def test_flex_deprecated_warns(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(
                hosting_plan=FLEX_CONSUMPTION_PLAN,
                app_settings={"SCM_DO_BUILD_DURING_DEPLOYMENT": "true"},
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert "SCM_DO_BUILD_DURING_DEPLOYMENT" in str(result["detail"])

    def test_flex_clean_passes(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(hosting_plan=FLEX_CONSUMPTION_PLAN),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "pass"

    def test_non_flex_skips(self, tmp_path: Path) -> None:
        context: RuleContext = {
            "target_config": _target_config(
                hosting_plan="linux-consumption",
                app_settings={"WEBSITE_CONTENTSHARE": "share"},
            ),
        }
        result = self._run(context, tmp_path)
        assert result["status"] == "skip"
