import json
from pathlib import Path

import pytest

from azure_functions_doctor.agent import (
    AgentFinding,
    AgentReportError,
    explain_failures,
    load_agent_report,
)


def _write_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "metadata": {"tool_version": "0.22.1"},
                "results": [
                    {
                        "title": "Python Env",
                        "category": "python_env",
                        "status": "fail",
                        "items": [
                            {
                                "rule_id": "check_python_runtime_lifecycle",
                                "label": "Python runtime lifecycle",
                                "value": "Python 3.10 is retiring",
                                "status": "fail",
                                "severity": "error",
                                "tier": "core",
                                "evidence": "Configured runtime is Python 3.10",
                                "expected": "A supported Python runtime",
                                "actual": "Python 3.10",
                                "source_url": "https://learn.microsoft.com/azure/functions/",
                                "last_verified": "2026-09-06",
                                "analysis": {"type": "deterministic"},
                            },
                            {
                                "rule_id": "check_host_json",
                                "label": "host.json",
                                "value": "host.json exists",
                                "status": "pass",
                                "severity": "error",
                                "tier": "core",
                                "analysis": {"type": "deterministic"},
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_load_agent_report_exposes_existing_json_and_sarif(tmp_path: Path) -> None:
    json_path = tmp_path / "doctor.json"
    sarif_path = tmp_path / "doctor.sarif"
    _write_report(json_path)
    sarif_path.write_text('{"version": "2.1.0", "runs": []}', encoding="utf-8")

    report = load_agent_report(json_path, sarif_path=sarif_path)

    assert report.schema_version == "2.0"
    assert report.sarif == {"version": "2.1.0", "runs": []}
    assert report.findings[0].rule_id == "check_python_runtime_lifecycle"


def test_explain_failures_uses_only_deterministic_evidence(tmp_path: Path) -> None:
    json_path = tmp_path / "doctor.json"
    _write_report(json_path)

    explanations = explain_failures(load_agent_report(json_path))

    assert explanations == (
        AgentFinding(
            rule_id="check_python_runtime_lifecycle",
            status="fail",
            summary="Python 3.10 is retiring",
            evidence="Configured runtime is Python 3.10",
            expected="A supported Python runtime",
            actual="Python 3.10",
            source_url="https://learn.microsoft.com/azure/functions/",
            last_verified="2026-09-06",
        ),
    )


def test_load_agent_report_rejects_pre_v2_contract(tmp_path: Path) -> None:
    json_path = tmp_path / "doctor.json"
    json_path.write_text(
        '{"schema_version": "1.0", "metadata": {}, "results": []}', encoding="utf-8"
    )

    with pytest.raises(AgentReportError, match="Finding Contract v2"):
        load_agent_report(json_path)


def test_load_agent_report_rejects_inferred_analysis(tmp_path: Path) -> None:
    json_path = tmp_path / "doctor.json"
    _write_report(json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["results"][0]["items"][0]["analysis"] = {"type": "llm"}
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AgentReportError, match="deterministic"):
        load_agent_report(json_path)
