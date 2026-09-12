"""Tests for Finding Contract v2 output (issue #348).

Covers the machine-output schema bump (``schema_version``), the deterministic
``analysis`` marker attached to every finding, threading of auditable evidence /
freshness fields from a handler result into a finding, their surfacing in JSON /
SARIF / human output, and the ``verified as of`` freshness rendering.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli as app
from azure_functions_doctor.doctor import (
    FINDING_SCHEMA_VERSION,
    CheckResult,
    Doctor,
    SectionResult,
    _apply_finding_contract_v2,
)
from azure_functions_doctor.handlers import HandlerResult
from azure_functions_doctor.utils import format_freshness_line

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# format_freshness_line
# ---------------------------------------------------------------------------


def test_format_freshness_line_with_source() -> None:
    line = format_freshness_line("2026-09-06", "https://learn.microsoft.com/azure")
    assert line == "verified as of 2026-09-06 — https://learn.microsoft.com/azure"


def test_format_freshness_line_without_source() -> None:
    assert format_freshness_line("2026-09-06") == "verified as of 2026-09-06"


def test_format_freshness_line_missing_date_is_empty() -> None:
    assert format_freshness_line("") == ""
    assert format_freshness_line("", "https://example.com") == ""


# ---------------------------------------------------------------------------
# _apply_finding_contract_v2
# ---------------------------------------------------------------------------


def test_apply_contract_copies_evidence_and_sets_analysis() -> None:
    item: CheckResult = {"rule_id": "r", "status": "fail"}
    result: HandlerResult = {
        "status": "fail",
        "evidence": "linuxFxVersion Python|3.9",
        "expected": ">=3.10",
        "actual": "3.9",
        "source_url": "https://learn.microsoft.com/azure",
        "last_verified": "2026-09-06",
        "catalog_version": "1.0.0",
    }
    _apply_finding_contract_v2(item, result)
    assert item["evidence"] == "linuxFxVersion Python|3.9"
    assert item["expected"] == ">=3.10"
    assert item["actual"] == "3.9"
    assert item["source_url"] == "https://learn.microsoft.com/azure"
    assert item["last_verified"] == "2026-09-06"
    assert item["catalog_version"] == "1.0.0"
    assert item["analysis"] == {"type": "deterministic"}


def test_apply_contract_sets_analysis_without_evidence() -> None:
    item: CheckResult = {"rule_id": "r", "status": "pass"}
    _apply_finding_contract_v2(item, {"status": "pass"})
    assert item["analysis"] == {"type": "deterministic"}
    assert "evidence" not in item
    assert "last_verified" not in item


def test_apply_contract_ignores_empty_evidence_values() -> None:
    item: CheckResult = {"rule_id": "r", "status": "fail"}
    _apply_finding_contract_v2(item, {"status": "fail", "evidence": ""})
    assert "evidence" not in item


# ---------------------------------------------------------------------------
# Every real finding carries the deterministic analysis marker
# ---------------------------------------------------------------------------


def _all_items(results: list[SectionResult]) -> list[CheckResult]:
    return [item for section in results for item in section["items"]]


def test_every_finding_has_deterministic_analysis(tmp_path: Path) -> None:
    doctor = Doctor(str(tmp_path))
    results = doctor.run_all_checks()
    items = _all_items(results)
    assert items  # non-v2 project short-circuits to at least one finding
    assert all(item.get("analysis") == {"type": "deterministic"} for item in items)


# ---------------------------------------------------------------------------
# JSON output: schema_version + analysis
# ---------------------------------------------------------------------------


def test_json_output_includes_schema_version_and_analysis() -> None:
    result = runner.invoke(
        app, ["doctor", "--path", str(FIXTURES_DIR / "unknown"), "--format", "json"]
    )
    data = json.loads(result.output)
    assert data["schema_version"] == FINDING_SCHEMA_VERSION
    findings = [item for section in data["results"] for item in section["items"]]
    assert findings
    assert all(item["analysis"]["type"] == "deterministic" for item in findings)


# ---------------------------------------------------------------------------
# SARIF output: analysis in properties
# ---------------------------------------------------------------------------


def test_sarif_findings_carry_deterministic_analysis() -> None:
    result = runner.invoke(
        app, ["doctor", "--path", str(FIXTURES_DIR / "unknown"), "--format", "sarif"]
    )
    data = json.loads(result.output)
    findings = data["runs"][0]["results"]
    assert findings
    for finding in findings:
        assert finding["properties"]["analysis"]["type"] == "deterministic"


# ---------------------------------------------------------------------------
# End-to-end evidence rendering (JSON / SARIF / human) via injected finding
# ---------------------------------------------------------------------------


def _synthetic_section() -> list[SectionResult]:
    item: CheckResult = {
        "rule_id": "python_runtime_lifecycle",
        "label": "Python runtime lifecycle",
        "value": "Python 3.10 support ends in October 2026",
        "status": "warn",
        "severity": "warning",
        "tier": "core",
        "evidence": "requires-python >=3.10",
        "expected": "supported runtime",
        "actual": "retiring-soon",
        "source_url": "https://learn.microsoft.com/azure/functions",
        "last_verified": "2026-09-06",
        "catalog_version": "1.0.0",
        "analysis": {"type": "deterministic"},
        "file": "pyproject.toml",
        "line": 3,
    }
    return [
        {
            "title": "Python Env",
            "category": "python_env",
            "status": "pass",
            "items": [item],
        }
    ]


@pytest.fixture
def _patched_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Doctor, "run_all_checks", lambda self, rules=None: _synthetic_section())


def test_json_surfaces_evidence_fields(_patched_checks: None, tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "json"])
    data = json.loads(result.output)
    finding = data["results"][0]["items"][0]
    assert finding["evidence"] == "requires-python >=3.10"
    assert finding["expected"] == "supported runtime"
    assert finding["actual"] == "retiring-soon"
    assert finding["source_url"] == "https://learn.microsoft.com/azure/functions"
    assert finding["last_verified"] == "2026-09-06"
    assert finding["catalog_version"] == "1.0.0"
    assert finding["analysis"]["type"] == "deterministic"


def test_sarif_surfaces_evidence_properties(_patched_checks: None, tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "sarif"])
    data = json.loads(result.output)
    props = data["runs"][0]["results"][0]["properties"]
    assert props["evidence"] == "requires-python >=3.10"
    assert props["source_url"] == "https://learn.microsoft.com/azure/functions"
    assert props["last_verified"] == "2026-09-06"
    assert props["catalog_version"] == "1.0.0"
    assert props["analysis"]["type"] == "deterministic"


def test_human_output_shows_verified_as_of(_patched_checks: None, tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "table"])
    assert "verified as of 2026-09-06" in result.output
    assert "https://learn.microsoft.com/azure/functions" in result.output
