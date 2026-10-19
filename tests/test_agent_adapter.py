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


# ---------------------------------------------------------------------------
# Config-suppressed findings stay adapter-compatible (#578)
# ---------------------------------------------------------------------------


def _write_single_rule_project(project: Path) -> None:
    project.mkdir()
    (project / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "@app.route(route='hello')\n"
        "def hello(req): return func.HttpResponse('ok')\n",
        encoding="utf-8",
    )
    (project / "host.json").write_text('{"version":"2.0"}', encoding="utf-8")
    (project / "requirements.txt").write_text("azure-functions>=1.20,<2\n", encoding="utf-8")


def _write_single_rule_file(rules_path: Path) -> None:
    rules_path.write_text(
        json.dumps(
            [
                {
                    "id": "check_missing_file",
                    "category": "structure",
                    "section": "project",
                    "label": "Required marker",
                    "description": "Check a local marker file",
                    "type": "file_exists",
                    "required": True,
                    "condition": {"target": "missing.marker"},
                    "check_order": 1,
                    "severity": "error",
                    "gate": True,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_cli_generated_report_with_suppressed_finding_loads_through_adapter(
    tmp_path: Path,
) -> None:
    """A real CLI-generated JSON report containing a config-suppressed
    (status=skip) item alongside it still loads through load_agent_report,
    instead of the whole report being rejected over one missing marker."""
    from typer.testing import CliRunner

    from azure_functions_doctor.cli import cli

    project = tmp_path / "project"
    _write_single_rule_project(project)
    rules_path = tmp_path / "rules.json"
    _write_single_rule_file(rules_path)
    (project / "pyproject.toml").write_text(
        '[tool.azure-functions-doctor]\nignore=["check_missing_file"]\n', encoding="utf-8"
    )
    output_path = tmp_path / "report.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "doctor",
            "--path",
            str(project),
            "--rules",
            str(rules_path),
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    report = load_agent_report(output_path)
    assert len(report.findings) == 1
    suppressed_finding = report.findings[0]
    assert suppressed_finding.rule_id == "check_missing_file"
    assert suppressed_finding.status == "skip"
    # Suppressed findings carry no failure evidence to explain and must not
    # appear in explain_failures (only warn/fail do).
    assert explain_failures(report) == ()
