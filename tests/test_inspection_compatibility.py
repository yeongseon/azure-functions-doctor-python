"""Byte baselines captured from origin/main 94f987f in a temporary git worktree.

Generate with DOCTOR_GOLDEN_SOURCE=<main-worktree>/src and DOCTOR_GOLDEN_RECORD=1.
Only project paths and generated_at timestamps are normalized. No main import is
performed during ordinary tests; the saved bytes and exit codes are authoritative.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

BASELINES = Path(__file__).parent / "fixtures" / "inspection-compatibility"
PROBE = """
import json, sys
from unittest.mock import patch
from typer.testing import CliRunner
from azure_functions_doctor.cli import cli
with patch('shutil.which', return_value=None):
    result = CliRunner().invoke(cli, ['doctor', '--path', sys.argv[1],
        '--format', sys.argv[2], '--target-python', '3.12'])
print(json.dumps({'code': result.exit_code, 'output': result.output}))
"""


@pytest.mark.parametrize("fixture", ["v2", "deploy", "langgraph"])
@pytest.mark.parametrize("output_format", ["table", "json", "sarif"])
def test_normal_project_matches_main_bytes(
    tmp_path: Path, fixture: str, output_format: str
) -> None:
    # Given normal regular-file projects, with in-root requirements includes.
    project = tmp_path / "project"
    project.mkdir()
    source = "import azure.functions as func\napp = func.FunctionApp()\n"
    if fixture == "langgraph":
        source = (
            "from azure_functions_langgraph import LangGraphApp\n"
            "adapter = LangGraphApp(graph=graph)\napp = adapter.function_app\n"
        )
    (project / "function_app.py").write_text(source)
    (project / "host.json").write_text(
        '{"version":"2.0","extensionBundle":{"id":"Microsoft.Azure.Functions.ExtensionBundle",'
        '"version":"[4.*, 5.0.0)"}}'
    )
    (project / "local.settings.json").write_text(
        '{"Values":{"FUNCTIONS_WORKER_RUNTIME":"python",'
        '"AzureWebJobsStorage":"UseDevelopmentStorage=true","FUNCTIONS_EXTENSION_VERSION":"~4"}}'
    )
    (project / "requirements.txt").write_text("azure-functions==1.21.3\n-r common.txt\n")
    (project / "common.txt").write_text("requests==2.32.5\n")
    (project / "pyproject.toml").write_text('[project]\nname="fixture"\ndependencies=[]\n')
    (project / "main.bicep").write_text("linuxFxVersion: 'Python|3.12'\n")
    if fixture == "deploy":
        (project / "infra.json").write_text(
            '{"functionAppConfig":{"runtime":{"name":"python","version":"3.12"},'
            '"deployment":{"storage":{"type":"blobContainer","value":"https://example.invalid",'
            '"authentication":{"type":"SystemAssignedIdentity"}}}}}'
        )
    env = {
        **os.environ,
        "PYTHONPATH": os.environ.get("DOCTOR_GOLDEN_SOURCE", str(Path("src").absolute())),
        "COLUMNS": "120",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    # When the real CLI renders each format in an isolated interpreter.
    run = subprocess.run(
        [sys.executable, "-c", PROBE, str(project), output_format],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(run.stdout)
    payload["output"] = payload["output"].replace(str(project), "<PROJECT>")
    payload["output"] = re.sub(
        r'("generated_at": ")[^"]+("|$)', r"\1<TIMESTAMP>\2", payload["output"]
    )
    saved = BASELINES / f"{fixture}-{output_format}.json"
    if os.environ.get("DOCTOR_GOLDEN_RECORD") == "1":
        saved.write_text(json.dumps(payload, indent=2) + "\n")
    # Then bytes and exit codes equal the baseline, not a recomputed main import.
    assert payload == json.loads(saved.read_text())
