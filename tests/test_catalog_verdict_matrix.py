"""Catalog-derived verdict matrix (issue #412).

Asserts that the lifecycle evaluators honor the version-controlled catalog
exhaustively: every (hosting plan x Python version) pair resolves through the
plan matrix, and every lifecycle verdict flips exactly at the catalog's
published boundary dates (retiring-soon window entry, end-of-support day, and
the day after). Expectations are *derived from the catalog*, not hardcoded,
so the matrix stays correct as the catalog rolls forward.
"""

from datetime import date, timedelta
from typing import Optional

import pytest

from azure_functions_doctor.compatibility import Catalog, SupportEnd, load_catalog
from azure_functions_doctor.handlers.runtime import (
    HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS,
    PYTHON_RETIRING_SOON_WINDOW_DAYS,
    _evaluate_functions_runtime_lifecycle,
    _evaluate_hosting_plan_lifecycle,
    _evaluate_python_lifecycle,
)
from azure_functions_doctor.target_resolver import is_supported_python_for_plan


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog()


def _last_day(support_end: SupportEnd) -> date:
    """The last calendar day the source guarantees (precision-widened)."""
    end = support_end.end_date()
    assert end is not None, support_end.value
    return end


class TestPlanPythonMatrix:
    """Every catalog (plan, version) pair resolves exactly per the matrix."""

    def test_known_plans_match_matrix_membership(self, catalog: Catalog) -> None:
        matrix = catalog.hosting_plan_matrix()
        versions = catalog.known_python_versions()
        assert matrix and versions
        for plan, allowed in matrix.items():
            for version in versions:
                expected = version in allowed
                assert is_supported_python_for_plan(version, plan) is expected, (
                    f"{plan} x {version}: expected supported={expected}"
                )

    def test_unknown_plan_falls_back_to_plan_agnostic_support(self, catalog: Catalog) -> None:
        for version in catalog.supported_python_versions():
            assert is_supported_python_for_plan(version, "does-not-exist") is True
        assert is_supported_python_for_plan("3.7", "does-not-exist") is False


class TestPythonLifecycleBoundaries:
    """Verdicts flip exactly at the catalog's published end-of-support dates."""

    def test_every_supported_version_is_supported_or_retiring_today(self, catalog: Catalog) -> None:
        """No supported version is ever past EOS on the current date."""
        today = date(2026, 9, 7)
        for version in catalog.supported_python_versions(as_of=today):
            result = _evaluate_python_lifecycle(version, today=today)
            # Raw evaluator contract: pass/info outside the window,
            # fail/warning (gate False -> canonical "warn") inside it.
            assert (result["status"], result.get("severity")) in (
                ("pass", "info"),
                ("fail", "warning"),
            ), (version, result["status"], result.get("severity"))
            assert result.get("gate") is not True, version

    def test_boundary_dates_for_each_fact(self, catalog: Catalog) -> None:
        today = date(2026, 9, 7)
        checked = 0
        for version in catalog.supported_python_versions(as_of=today):
            eos = catalog.python_eos(version)
            if eos is None:
                continue
            checked += 1
            last_day = _last_day(eos)
            window_start = last_day - timedelta(days=PYTHON_RETIRING_SOON_WINDOW_DAYS)

            before = _evaluate_python_lifecycle(version, today=window_start - timedelta(days=1))
            assert (before["status"], before.get("severity")) == ("pass", "info"), (
                version,
                "before window",
                before,
            )

            inside = _evaluate_python_lifecycle(version, today=window_start + timedelta(days=1))
            assert (inside["status"], inside.get("severity")) == ("fail", "warning"), (
                version,
                "inside window",
                inside,
            )
            assert inside.get("gate") is False  # canonical "warn", never gating

            after = _evaluate_python_lifecycle(version, today=last_day + timedelta(days=1))
            assert (after["status"], after.get("severity")) == ("fail", "error"), (
                version,
                "past eos",
                after,
            )
            assert after.get("gate") is True

        assert checked >= 5, "expected every supported Python to carry an EOS fact"


class TestHostingPlanLifecycleBoundaries:
    """Plan verdicts flip at the catalog's retirement dates."""

    def test_plan_boundaries(self, catalog: Catalog) -> None:
        matrix = catalog.hosting_plan_matrix()
        checked = 0
        for plan in matrix:
            fact = catalog.hosting_plan_lifecycle_fact(plan)
            if fact is None or fact.support_end is None:
                # No published retirement: the plan must never fail on dates.
                result = _evaluate_hosting_plan_lifecycle(plan, today=date(2030, 1, 1))
                assert result["status"] in ("pass", "warn", "skip"), (plan, result)
                continue
            checked += 1
            last_day = _last_day(fact.support_end)
            window_start = last_day - timedelta(days=HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS)
            before = _evaluate_hosting_plan_lifecycle(plan, today=window_start - timedelta(days=1))
            assert (before["status"], before.get("severity")) == ("pass", "info"), (plan, before)

            inside = _evaluate_hosting_plan_lifecycle(plan, today=window_start + timedelta(days=1))
            assert (inside["status"], inside.get("severity")) == ("fail", "warning"), (plan, inside)
            assert inside.get("gate") is False

            after = _evaluate_hosting_plan_lifecycle(plan, today=last_day + timedelta(days=1))
            assert (after["status"], after.get("severity")) == ("fail", "error"), (plan, after)
            assert after.get("gate") is True

        assert checked >= 1, "expected at least one plan with a retirement date"


class TestFunctionsRuntimeVerdicts:
    """Runtime verdicts match the catalog's per-runtime facts."""

    @pytest.mark.parametrize(
        ("runtime", "expected_status", "expected_severity"),
        [
            ("~1", "fail", "error"),  # incompatible with Python
            ("~2", "fail", "error"),  # out of support
            ("~3", "fail", "error"),  # out of support
            ("4", "pass", "info"),  # pinned forms normalize to 4.x
            ("~4", "pass", "info"),
        ],
    )
    def test_runtime_verdicts(
        self,
        catalog: Catalog,
        runtime: str,
        expected_status: str,
        expected_severity: str,
    ) -> None:
        result = _evaluate_functions_runtime_lifecycle(
            runtime,
            None,
            today=date(2026, 9, 7),
            catalog=catalog,
        )
        assert result["status"] == expected_status, (runtime, result)
        assert result.get("severity") == expected_severity, (runtime, result)

    def test_undeterminable_runtime_skips(self, catalog: Catalog) -> None:
        result = _evaluate_functions_runtime_lifecycle(
            None, None, today=date(2026, 9, 7), catalog=catalog
        )
        assert result["status"] == "skip"

    def test_linux_consumption_v3_stop_date_escalates(self, catalog: Catalog) -> None:
        fact = catalog.functions_runtime_plan_fact("3.x", "linux-consumption")
        assert fact is not None and fact.support_end is not None
        after = _evaluate_functions_runtime_lifecycle(
            "~3",
            "linux-consumption",
            today=_last_day(fact.support_end) + timedelta(days=1),
            catalog=catalog,
        )
        assert after["status"] == "fail"
        assert after.get("severity") == "error"
        detail = str(after.get("detail", ""))
        assert "stop" in detail.lower() or "v3" in detail


def _optional_fact(catalog: Catalog, plan: str) -> Optional[object]:
    return catalog.hosting_plan_lifecycle_fact(plan)
