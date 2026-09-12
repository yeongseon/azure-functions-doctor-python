"""Tests for the Functions runtime and hosting-plan lifecycle checks (issue #344)."""

from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from azure_functions_doctor.compatibility import load_catalog
from azure_functions_doctor.deploy_config import ResolvedField, TargetConfig
from azure_functions_doctor.handlers._helpers import RuleContext
from azure_functions_doctor.handlers.registry import (
    HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS,
    HandlerRegistry,
    _evaluate_functions_runtime_lifecycle,
    _evaluate_hosting_plan_lifecycle,
    _normalize_functions_runtime,
)

# Reference "today" in project context: before every runtime/hosting retirement.
TODAY = date(2026, 9, 6)
SUPPORTED_LANGUAGES = "https://learn.microsoft.com/azure/azure-functions/supported-languages"


def _target_config(
    *,
    extension_version: Optional[str] = None,
    hosting_plan: Optional[str] = None,
) -> TargetConfig:
    """Build a minimal :class:`TargetConfig` for handler-level tests."""
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


class TestNormalizeFunctionsRuntime:
    def test_pinned_tilde_form(self) -> None:
        assert _normalize_functions_runtime("~4") == "4.x"

    def test_plain_major(self) -> None:
        assert _normalize_functions_runtime("3") == "3.x"

    def test_full_version_uses_major(self) -> None:
        assert _normalize_functions_runtime("4.0.1") == "4.x"

    def test_none_and_empty(self) -> None:
        assert _normalize_functions_runtime(None) is None
        assert _normalize_functions_runtime("") is None

    def test_unparseable(self) -> None:
        assert _normalize_functions_runtime("latest") is None


class TestEvaluateFunctionsRuntimeLifecycle:
    def test_unknown_runtime_skips(self) -> None:
        result = _evaluate_functions_runtime_lifecycle(None, None, today=TODAY)
        assert result["status"] == "skip"
        assert "could not be determined" in result["detail"]

    def test_v4_passes(self) -> None:
        result = _evaluate_functions_runtime_lifecycle("~4", None, today=TODAY)
        assert result["status"] == "pass"
        assert result["severity"] == "info"
        assert result["gate"] is False
        assert "v4" in result["detail"]

    def test_v1_fails_as_incompatible_with_python(self) -> None:
        result = _evaluate_functions_runtime_lifecycle("~1", "flex-consumption", today=TODAY)
        assert result["status"] == "fail"
        assert result["severity"] == "error"
        assert result["gate"] is True
        assert "not compatible with Python" in result["detail"]
        # Lifecycle note added, rendered at the catalog's day precision.
        assert "September 14, 2026" in result["detail"]
        assert result["source_url"]

    def test_v2_out_of_support(self) -> None:
        result = _evaluate_functions_runtime_lifecycle("~2", None, today=TODAY)
        assert result["status"] == "fail"
        assert result["severity"] == "error"
        assert result["gate"] is True
        assert "out of support" in result["detail"]
        assert "December 13, 2022" in result["detail"]

    def test_v3_non_linux_out_of_support(self) -> None:
        result = _evaluate_functions_runtime_lifecycle("~3", "premium", today=TODAY)
        assert result["status"] == "fail"
        assert "runtime v3 is out of support" in result["detail"]

    def test_v3_on_linux_consumption_emphasises_stop_date(self) -> None:
        result = _evaluate_functions_runtime_lifecycle("~3", "linux-consumption", today=TODAY)
        assert result["status"] == "fail"
        assert result["severity"] == "error"
        assert result["gate"] is True
        assert "stop running after September 30, 2026" in result["detail"]
        assert result["actual"] == "Azure Functions runtime v3 on Linux Consumption"

    def test_explicit_catalog_is_honored(self) -> None:
        catalog = load_catalog()
        result = _evaluate_functions_runtime_lifecycle("~4", None, today=TODAY, catalog=catalog)
        assert result["catalog_version"] == catalog.catalog_version


class TestEvaluateHostingPlanLifecycle:
    def test_unknown_plan_skips(self) -> None:
        result = _evaluate_hosting_plan_lifecycle(None, today=TODAY)
        assert result["status"] == "skip"

    def test_plan_without_retirement_passes(self) -> None:
        result = _evaluate_hosting_plan_lifecycle("premium", today=TODAY)
        assert result["status"] == "pass"
        assert "no published retirement" in result["detail"]

    def test_linux_consumption_far_off_is_informational(self) -> None:
        result = _evaluate_hosting_plan_lifecycle("linux-consumption", today=TODAY)
        assert result["status"] == "pass"
        assert result["severity"] == "info"
        assert result["gate"] is False
        assert "September 30, 2028" in result["detail"]
        assert "Flex Consumption" in result["detail"]

    def test_linux_consumption_within_window_warns(self) -> None:
        fact = load_catalog().hosting_plan_lifecycle_fact("linux-consumption")
        assert fact is not None and fact.support_end is not None
        end = fact.support_end.end_date()
        assert end is not None
        within = end - timedelta(days=HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS - 1)
        result = _evaluate_hosting_plan_lifecycle("linux-consumption", today=within)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False

    def test_linux_consumption_past_retirement_fails(self) -> None:
        result = _evaluate_hosting_plan_lifecycle("linux-consumption", today=date(2028, 10, 1))
        assert result["status"] == "fail"
        assert result["severity"] == "error"
        assert result["gate"] is True
        assert "retired on September 30, 2028" in result["detail"]


class TestCatalogHelpers:
    def test_functions_runtime_fact(self) -> None:
        fact = load_catalog().functions_runtime_fact("4.x")
        assert fact is not None
        assert fact.applies_to["functions_runtime"] == "4.x"
        assert "hosting_plan" not in fact.applies_to

    def test_functions_runtime_fact_unknown(self) -> None:
        assert load_catalog().functions_runtime_fact("9.x") is None

    def test_functions_runtime_plan_fact(self) -> None:
        fact = load_catalog().functions_runtime_plan_fact("3.x", "linux-consumption")
        assert fact is not None
        assert fact.applies_to["hosting_plan"] == "linux-consumption"

    def test_functions_runtime_plan_fact_unknown(self) -> None:
        assert load_catalog().functions_runtime_plan_fact("4.x", "premium") is None

    def test_hosting_plan_lifecycle_fact(self) -> None:
        fact = load_catalog().hosting_plan_lifecycle_fact("linux-consumption")
        assert fact is not None

    def test_hosting_plan_lifecycle_fact_unknown(self) -> None:
        assert load_catalog().hosting_plan_lifecycle_fact("premium") is None


class TestHandlerWiring:
    """Handler-level tests exercising context resolution."""

    def _run(self, method: str, context: Optional[RuleContext]) -> dict[str, object]:
        registry = HandlerRegistry()
        handler = getattr(registry, method)
        with patch("azure_functions_doctor.handlers.runtime.date") as mock_date:
            mock_date.today.return_value = TODAY
            return dict(handler({}, Path("."), context))

    def test_runtime_handler_reads_extension_version(self) -> None:
        context: RuleContext = {
            "target_config": _target_config(extension_version="~1", hosting_plan="premium"),
        }
        result = self._run("_handle_functions_runtime_lifecycle", context)
        assert result["status"] == "fail"
        assert "not compatible with Python" in str(result["detail"])

    def test_runtime_handler_without_context_skips(self) -> None:
        result = self._run("_handle_functions_runtime_lifecycle", None)
        assert result["status"] == "skip"

    def test_hosting_handler_reads_plan(self) -> None:
        context: RuleContext = {
            "target_config": _target_config(hosting_plan="linux-consumption"),
        }
        result = self._run("_handle_hosting_plan_lifecycle", context)
        assert result["status"] == "pass"
        assert "September 30, 2028" in str(result["detail"])

    def test_hosting_handler_without_context_skips(self) -> None:
        result = self._run("_handle_hosting_plan_lifecycle", None)
        assert result["status"] == "skip"
