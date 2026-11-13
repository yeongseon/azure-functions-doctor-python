"""Smoke tests for the credential-free SARIF CI example (issue #661).

The workflow's doctor command is extracted from ``examples/github-actions`` and executed
offline; the SARIF it writes is checked with the example's stdlib-only structural validator
(not the full SARIF JSON Schema, which needs network access).
"""

import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = ROOT / "examples" / "github-actions"
WORKFLOW = EXAMPLE_DIR / "azure-functions-sarif-artifact.yml"
VALIDATOR = EXAMPLE_DIR / "check_sarif_shape.py"

runner = CliRunner()


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_sarif_shape", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workflow_doctor_args(output: Path) -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"^\s+azure-functions-doctor (doctor .+)$", text, flags=re.MULTILINE)
    assert match, "doctor command not found in workflow"
    args = shlex.split(match.group(1))
    assert args[args.index("--output") + 1] == "doctor.sarif"
    args[args.index("--output") + 1] = str(output)
    return args


def _generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, Path]:
    monkeypatch.chdir(ROOT)  # the workflow runs from the repository root
    output = tmp_path / "doctor.sarif"
    result = runner.invoke(cli, _workflow_doctor_args(output))
    return result.exit_code, output


def test_workflow_command_emits_expected_nonzero_exit_and_valid_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exit_code, output = _generate(tmp_path, monkeypatch)
    assert exit_code == 1  # required checks fail on the broken example
    document = json.loads(output.read_text(encoding="utf-8"))
    assert _load_validator().check_sarif_shape(document) == []
    results = document["runs"][0]["results"]
    assert {r["ruleId"] for r in results} >= {"check_host_json"}
    assert all(r["level"] == "error" for r in results)


def test_validator_script_passes_generated_file_and_fails_malformed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, output = _generate(tmp_path, monkeypatch)
    ok = subprocess.run([sys.executable, str(VALIDATOR), str(output)], capture_output=True)
    assert ok.returncode == 0
    assert b"not full JSON Schema validation" in ok.stdout

    broken = tmp_path / "broken.sarif"
    broken.write_text('{"version": "1.0", "runs": []}', encoding="utf-8")
    bad = subprocess.run([sys.executable, str(VALIDATOR), str(broken)], capture_output=True)
    assert bad.returncode == 1
    assert b"version must be" in bad.stderr


def _mutate(document: dict[str, Any], change: str) -> dict[str, Any]:
    run = document["runs"][0]
    if change == "level":
        run["results"][0]["level"] = "fatal"
    elif change == "ruleId":
        run["results"][0]["ruleId"] = "not_a_rule"
    elif change == "message":
        run["results"][0]["message"] = {}
    elif change == "driver":
        run["tool"]["driver"].pop("name")
    elif change == "uri":
        run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"].pop("uri")
    elif change == "duplicate":
        run["tool"]["driver"]["rules"].append(dict(run["tool"]["driver"]["rules"][0]))
    return document


@pytest.mark.parametrize("change", ["level", "ruleId", "message", "driver", "uri", "duplicate"])
def test_validator_rejects_structural_damage(
    change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, output = _generate(tmp_path, monkeypatch)
    document = _mutate(json.loads(output.read_text(encoding="utf-8")), change)
    assert _load_validator().check_sarif_shape(document)


def test_workflow_is_credential_free_and_preserves_artifact_on_failure() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "secrets." not in code
    assert "security-events" not in code and "upload-sarif" not in code
    assert "permissions:\n  contents: read" in text
    assert "set +e" in text  # findings must not stop the run before the artifact upload
    upload = text.split("actions/upload-artifact")[0].rsplit("- name:", 1)[1]
    assert "if: always()" in upload
    assert "--format sarif" in text and "Expected result" in text


def test_ci_docs_describe_the_example_and_its_schema_limit() -> None:
    docs = (ROOT / "docs" / "examples" / "ci_integration.md").read_text(encoding="utf-8")
    section = docs.split("## Credential-free SARIF artifact")[1].split("\n## ")[0]
    assert "azure-functions-sarif-artifact.yml" in section
    assert "check_sarif_shape.py" in section
    assert "structural" in section and "not full" in section
    assert "exit code `1`" in section
