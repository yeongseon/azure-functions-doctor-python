"""Gate/severity independence regression at the public CLI boundary (issue #310).

Doctor.run_all_checks() correctly derives section["status"] from the
resolved ``gate`` (independent of display severity). Before this fix, all
four CLI output formats (json, sarif, junit, table) computed their process
exit code from a count of items whose *severity* mapped to "fail",
ignoring the section gate result -- so a declared gate could pass CI while
a deliberately non-gating diagnostic could fail it. This file exercises
the real CLI with schema-valid custom rules covering the two controls
(``gate``, ``required``) and the two combinations where they conflict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET  # nosec B405

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli as app

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "@app.route(route='hello')\n"
        "def hello(req): return func.HttpResponse('ok')\n",
        encoding="utf-8",
    )
    (root / "host.json").write_text('{"version":"2.0"}', encoding="utf-8")
    (root / "requirements.txt").write_text("azure-functions>=1.20,<2\n", encoding="utf-8")
    return root


def _rule(*, severity: str, gate: bool, required: bool) -> dict[str, Any]:
    return {
        "id": "check_missing_file",
        "category": "structure",
        "section": "project",
        "label": "Required marker",
        "description": "Check a local marker file",
        "type": "file_exists",
        "required": required,
        "condition": {"target": "missing.marker"},
        "check_order": 1,
        "severity": severity,
        "gate": gate,
    }


def _rules_file(tmp_path: Path, **kwargs: Any) -> Path:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps([_rule(**kwargs)]), encoding="utf-8")
    return rules_path


# (severity, gate, required, expected exit code) -- the two conflicting
# combinations (gate != required) are the cases this issue's fix targets.
GATE_SEVERITY_CASES = [
    pytest.param("error", True, True, 1, id="gate-true_required-true_error"),
    pytest.param("warning", False, False, 0, id="gate-false_required-false_warning"),
    pytest.param("warning", True, False, 1, id="gate-true_required-false_warning_conflict"),
    pytest.param("error", False, True, 0, id="gate-false_required-true_error_conflict"),
]


class TestGateIndependentOfSeverityJson:
    @pytest.mark.parametrize("severity,gate,required,expected_exit", GATE_SEVERITY_CASES)
    def test_json_exit_code_follows_gate_not_severity(
        self,
        tmp_path: Path,
        severity: str,
        gate: bool,
        required: bool,
        expected_exit: int,
    ) -> None:
        project = _project(tmp_path)
        rules = _rules_file(tmp_path, severity=severity, gate=gate, required=required)
        result = runner.invoke(
            app, ["doctor", "--path", str(project), "--rules", str(rules), "--format", "json"]
        )

        assert result.exit_code == expected_exit
        data = json.loads(result.output)
        section = data["results"][0]
        assert section["status"] == ("fail" if gate else "pass")
        assert data["metadata"]["gate_failed"] is (expected_exit == 1)


class TestGateIndependentOfSeverityOtherFormats:
    @pytest.mark.parametrize("severity,gate,required,expected_exit", GATE_SEVERITY_CASES)
    def test_sarif_exit_code_follows_gate_not_severity(
        self,
        tmp_path: Path,
        severity: str,
        gate: bool,
        required: bool,
        expected_exit: int,
    ) -> None:
        project = _project(tmp_path)
        rules = _rules_file(tmp_path, severity=severity, gate=gate, required=required)
        result = runner.invoke(
            app, ["doctor", "--path", str(project), "--rules", str(rules), "--format", "sarif"]
        )

        assert result.exit_code == expected_exit
        sarif = json.loads(result.output)
        assert sarif["runs"][0]["properties"]["gate_failed"] is (expected_exit == 1)

    @pytest.mark.parametrize("severity,gate,required,expected_exit", GATE_SEVERITY_CASES)
    def test_junit_exit_code_follows_gate_not_severity(
        self,
        tmp_path: Path,
        severity: str,
        gate: bool,
        required: bool,
        expected_exit: int,
    ) -> None:
        project = _project(tmp_path)
        rules = _rules_file(tmp_path, severity=severity, gate=gate, required=required)
        result = runner.invoke(
            app, ["doctor", "--path", str(project), "--rules", str(rules), "--format", "junit"]
        )

        assert result.exit_code == expected_exit
        root = ET.fromstring(result.output)  # nosec B314
        gate_prop = root.find("./properties/property[@name='gate_failed']")
        assert gate_prop is not None
        assert gate_prop.get("value") == str(expected_exit == 1).lower()

    @pytest.mark.parametrize("severity,gate,required,expected_exit", GATE_SEVERITY_CASES)
    def test_table_exit_code_follows_gate_not_severity(
        self,
        tmp_path: Path,
        severity: str,
        gate: bool,
        required: bool,
        expected_exit: int,
    ) -> None:
        project = _project(tmp_path)
        rules = _rules_file(tmp_path, severity=severity, gate=gate, required=required)
        result = runner.invoke(
            app, ["doctor", "--path", str(project), "--rules", str(rules), "--format", "table"]
        )

        assert result.exit_code == expected_exit

    def test_summary_json_sidecar_carries_gate_failed(self, tmp_path: Path) -> None:
        project = _project(tmp_path)
        rules = _rules_file(tmp_path, severity="warning", gate=True, required=False)
        summary_path = tmp_path / "summary.json"
        result = runner.invoke(
            app,
            [
                "doctor",
                "--path",
                str(project),
                "--rules",
                str(rules),
                "--format",
                "json",
                "--summary-json",
                str(summary_path),
            ],
        )

        assert result.exit_code == 1
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["gate_failed"] is True
