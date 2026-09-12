"""Tests for the date-based Python runtime lifecycle check (issue #343)."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from azure_functions_doctor.compatibility import load_catalog
from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers.registry import (
    PYTHON_RETIRING_SOON_WINDOW_DAYS,
    _evaluate_python_lifecycle,
)

EXAMPLE_V2 = Path(__file__).resolve().parent.parent / "examples" / "v2" / "http-trigger"

# A date well before every catalog end-of-support (all EOS are 2026-10 or later),
# yet within the retiring-soon window of the earliest (Python 3.10, Oct 2026).
BEFORE_ANY_EOS = date(2026, 9, 6)
# A date after Python 3.10's end-of-support (Oct 2026) but before 3.11's (Oct 2027).
AFTER_310_EOS = date(2026, 11, 1)


class TestEvaluatePythonLifecycle:
    """Unit tests for the pure ``_evaluate_python_lifecycle`` classifier."""

    def test_supported_version_passes_with_month_precision(self) -> None:
        result = _evaluate_python_lifecycle("3.12", today=BEFORE_ANY_EOS)
        assert result["status"] == "pass"
        assert result["severity"] == "info"
        assert result["gate"] is False
        # Rendered at month precision: no invented day or countdown.
        assert "October 2028" in result["detail"]
        assert "remaining" not in result["detail"]
        assert (
            result["source_url"]
            == "https://learn.microsoft.com/azure/azure-functions/supported-languages"
        )
        assert result["last_verified"] == "2026-09-06"
        assert result["catalog_version"] == "1.0.0"

    def test_retiring_soon_warns_without_gating(self) -> None:
        result = _evaluate_python_lifecycle("3.10", today=BEFORE_ANY_EOS)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"
        assert result["gate"] is False
        assert "expected to end in October 2026" in result["detail"]
        # Month precision only — never a specific day or day countdown.
        assert "October 2026" in result["actual"]
        assert "days" not in result["detail"]

    def test_unsupported_version_fails_and_gates(self) -> None:
        result = _evaluate_python_lifecycle("3.10", today=AFTER_310_EOS)
        assert result["status"] == "fail"
        assert result["severity"] == "error"
        assert result["gate"] is True
        assert "past Azure Functions end-of-support" in result["detail"]
        assert "October 2026" in result["detail"]

    def test_upgrade_recommendation_is_catalog_derived(self) -> None:
        """The recommendation names the catalog's newest supported Python (#382 review)."""
        catalog = load_catalog()
        newest = catalog.supported_python_versions(as_of=BEFORE_ANY_EOS)[-1]

        retiring = _evaluate_python_lifecycle("3.10", today=BEFORE_ANY_EOS)
        assert f"(e.g. {newest})" in retiring["detail"]
        # No Azure version knowledge is hardcoded in the handler strings.
        assert "3.12+" not in retiring["detail"]
        assert retiring["expected"] == "A supported Azure Functions Python runtime"

        unsupported = _evaluate_python_lifecycle("3.10", today=AFTER_310_EOS)
        assert f"(e.g. {newest})" in unsupported["detail"]
        assert "3.12+" not in unsupported["detail"]

    def test_unknown_version_is_neutral(self) -> None:
        result = _evaluate_python_lifecycle("3.15", today=BEFORE_ANY_EOS)
        assert result["status"] == "pass"
        assert "no catalog lifecycle data" in result["detail"]
        # No evidence fields are emitted when there is no catalog fact.
        assert "source_url" not in result
        assert "severity" not in result

    def test_patch_version_is_normalized(self) -> None:
        result = _evaluate_python_lifecycle("3.10.12", today=BEFORE_ANY_EOS)
        assert result["status"] == "fail"
        assert result["severity"] == "warning"

    def test_retiring_soon_threshold_boundary(self) -> None:
        """The retiring-soon window boundary is inclusive at month precision."""
        catalog = load_catalog()
        eos = catalog.python_eos("3.10")
        assert eos is not None
        end = eos.end_date()
        assert end is not None

        on_edge = end - timedelta(days=PYTHON_RETIRING_SOON_WINDOW_DAYS)
        before_edge = on_edge - timedelta(days=1)

        assert _evaluate_python_lifecycle("3.10", today=on_edge)["status"] == "fail"
        assert _evaluate_python_lifecycle("3.10", today=before_edge)["status"] == "pass"

    def test_explicit_catalog_is_honored(self) -> None:
        catalog = load_catalog()
        result = _evaluate_python_lifecycle("3.11", today=BEFORE_ANY_EOS, catalog=catalog)
        assert result["status"] == "pass"
        assert "October 2027" in result["detail"]


class TestCatalogLifecycleFact:
    """Tests for the catalog helper backing the lifecycle check."""

    def test_python_lifecycle_fact_returns_fact(self) -> None:
        fact = load_catalog().python_lifecycle_fact("3.10")
        assert fact is not None
        assert fact.applies_to["python"] == "3.10"
        assert fact.support_end is not None

    def test_python_lifecycle_fact_unknown_returns_none(self) -> None:
        assert load_catalog().python_lifecycle_fact("3.15") is None

    def test_python_lifecycle_fact_malformed_returns_none(self) -> None:
        assert load_catalog().python_lifecycle_fact("not-a-version") is None


class TestLifecycleHandlerIntegration:
    """End-to-end tests wiring the handler through the Doctor run."""

    def _lifecycle_item(self, today: date) -> dict[str, object]:
        doctor = Doctor(str(EXAMPLE_V2), target_python="3.10")
        with patch("azure_functions_doctor.handlers.runtime.date") as mock_date:
            mock_date.today.return_value = today
            results = doctor.run_all_checks()
        for section in results:
            for item in section["items"]:
                if item["rule_id"] == "check_python_runtime_lifecycle":
                    return dict(item)
        raise AssertionError("lifecycle finding not emitted")

    def test_retiring_runtime_surfaces_as_warning(self) -> None:
        item = self._lifecycle_item(BEFORE_ANY_EOS)
        assert item["status"] == "warn"
        assert item["severity"] == "warning"
        assert item["analysis"] == {"type": "deterministic"}
        assert item["last_verified"] == "2026-09-06"
        assert item["catalog_version"] == "1.0.0"

    def test_unsupported_runtime_gates_the_section(self) -> None:
        doctor = Doctor(str(EXAMPLE_V2), target_python="3.10")
        with patch("azure_functions_doctor.handlers.runtime.date") as mock_date:
            mock_date.today.return_value = AFTER_310_EOS
            results = doctor.run_all_checks()
        section = next(s for s in results if s["category"] == "python_env")
        item = next(i for i in section["items"] if i["rule_id"] == "check_python_runtime_lifecycle")
        assert item["status"] == "fail"
        assert item["severity"] == "error"
        # A gating failure marks the whole section failed.
        assert section["status"] == "fail"
