"""Offline Python-runtime x hosting-plan comparison on one synthetic project (issue #664).

The matrix runs the checked-in ``examples/v2/http-trigger`` project through the CLI with two
hosting plans and two Python targets. Expected values are derived from the compatibility
catalog (never hardcoded Azure claims), and "today" is pinned so the runtime/plan lifecycle
verdicts cannot flip as the calendar passes catalog dates.

Gap audited: ``tests/test_catalog_verdict_matrix.py`` and
``tests/test_runtime_deploy_risk_rules.py`` cover the plan x version matrix and input
validation at function level, and
``tests/test_runtime_hosting_lifecycle.py`` covers each lifecycle evaluator in isolation, but
no test shows the combined CLI-level result for one project. See ``docs/runtime_hosting_matrix.md``.
"""

from datetime import date
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli
from azure_functions_doctor.compatibility import load_catalog
from azure_functions_doctor.target_resolver import is_supported_python_for_plan

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "examples" / "v2" / "http-trigger"
PAGE = ROOT / "docs" / "runtime_hosting_matrix.md"
TODAY = date(2026, 9, 6)  # before every runtime/hosting retirement in the catalog
MATRIX = [
    ("linux-consumption", "3.12"),
    ("linux-consumption", "3.13"),
    ("flex-consumption", "3.12"),
    ("flex-consumption", "3.13"),
]

runner = CliRunner()


def _run(plan: str, version: str) -> Any:
    args = [
        "doctor",
        "--path",
        str(PROJECT),
        "--profile",
        "deploy",
        "--hosting-plan",
        plan,
        "--target-python",
        version,
        "--format",
        "json",
    ]
    with patch("azure_functions_doctor.handlers.runtime.date") as mock_date:
        mock_date.today.return_value = TODAY
        return runner.invoke(cli, args)


def _items(output: str) -> dict[str, dict[str, Any]]:
    report = json.loads(output)
    return {item["rule_id"]: item for section in report["results"] for item in section["items"]}


@pytest.mark.parametrize(("plan", "version"), MATRIX)
def test_cli_exit_follows_catalog_plan_matrix(plan: str, version: str) -> None:
    result = _run(plan, version)
    if is_supported_python_for_plan(version, plan):
        assert result.exit_code == 0, result.output
    else:
        # The combination is rejected before any rule runs: a usage error, not a finding.
        assert result.exit_code == 2
        assert "is not supported on" in result.output
        assert plan in result.output


@pytest.mark.parametrize(
    ("plan", "version"),
    [pair for pair in MATRIX if is_supported_python_for_plan(pair[1], pair[0])],
)
def test_python_lifecycle_is_version_bound_not_plan_bound(plan: str, version: str) -> None:
    item = _items(_run(plan, version).output)["check_python_runtime_lifecycle"]
    eos = load_catalog().python_eos(version)
    assert eos is not None
    assert item["status"] == "pass"
    assert f"Python {version} is supported" in item["value"]
    assert eos.render() in item["value"]


def test_hosting_plan_lifecycle_differs_by_plan_from_catalog_dates() -> None:
    catalog = load_catalog()
    linux = _items(_run("linux-consumption", "3.12").output)["check_hosting_plan_lifecycle"]
    flex = _items(_run("flex-consumption", "3.12").output)["check_hosting_plan_lifecycle"]
    retirement = catalog.hosting_plan_lifecycle_fact("linux-consumption")
    assert retirement is not None and retirement.support_end is not None
    assert linux["status"] == "pass"
    assert retirement.support_end.render() in linux["value"]
    assert catalog.hosting_plan_lifecycle_fact("flex-consumption") is None
    assert flex["status"] == "pass"
    assert "no published retirement date" in flex["value"]


def test_page_documents_the_matrix_and_the_update_guide() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for plan, version in MATRIX:
        assert f"--hosting-plan {plan} --target-python {version}" in text
    assert "## Updating when the support catalog changes" in text
    assert "compatibility catalog" in text
