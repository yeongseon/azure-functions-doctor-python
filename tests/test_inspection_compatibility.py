"""Byte baselines captured from origin/main 94f987f in a temporary git worktree.

Generate with DOCTOR_GOLDEN_SOURCE=<main-worktree>/src and DOCTOR_GOLDEN_RECORD=1.
The child environment is allowlisted and external executable discovery is fixed.
Paths, timestamps, package versions and tool-runtime Python versions alone are
normalized; finding text, order, whitespace, counts and exit codes remain byte-pinned.
"""

import difflib
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
with patch('shutil.which', return_value=None), patch('sys.executable', 'python'):
    result = CliRunner().invoke(cli, ['doctor', '--path', sys.argv[1],
        '--format', sys.argv[2], '--target-python', '3.12'])
print(json.dumps({'code': result.exit_code, 'output': result.output}))
"""


@pytest.mark.parametrize(
    "fixture",
    [
        "v2",
        "deploy",
        "langgraph",
        "chain",
        "dotdot",
        "diamond",
        "symlink",
        "multilevel",
        "root-symlink",
        "alias-base",
        "bom-include",
        "included-alias-base",
        "bom-child",
        "crlf",
        "alias-integration",
        "alias-gap",
        "bom-funcignore",
    ],
)
@pytest.mark.parametrize("output_format", ["table", "json", "sarif"])
def test_normal_project_matches_main_bytes(
    tmp_path: Path, fixture: str, output_format: str
) -> None:
    # Given normal regular-file projects, with in-root requirements includes.
    project = tmp_path / "project"
    project.mkdir()
    (project / "python").write_text("")
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
    if fixture in {"chain", "dotdot", "diamond", "symlink", "multilevel", "root-symlink"}:
        (project / "sub").mkdir()
        (project / "nested").mkdir()
        (project / "common.txt").write_text("numpy\n")
        requirements = "azure-functions==1.21.3\n"
        if fixture in {"chain", "root-symlink"}:
            requirements += "-r sub/child.txt\n"
            (project / "sub/child.txt").write_text("requests==2.32.5\n-r ../common.txt\n")
        elif fixture == "dotdot":
            requirements += "-r nested/../common.txt\n"
        elif fixture == "diamond":
            requirements += "-r sub/left.txt\n-r sub/right.txt\n-r ./common.txt\n"
            for branch in ("left", "right"):
                (project / f"sub/{branch}.txt").write_text("-r ../common.txt\n")
        elif fixture == "symlink":
            (project / "alias.txt").symlink_to(project / "common.txt")
            requirements += "-r alias.txt\n"
        else:
            requirements += "-r ./sub/child.txt\n-r sub/../common.txt\n"
            (project / "sub/child.txt").write_text("-r ../nested/deps.txt\n-c ../constraints.txt\n")
            (project / "nested/deps.txt").write_text(
                "azure-functions-worker\nazure-functions-validation\n"
                "azure-functions-logging[otel]\n-r ../common.txt\n"
            )
            (project / "constraints.txt").write_text("requests==2.32.5\n")
            (project / "function_app.py").write_text(
                "import azure.functions as func\n"
                "from azure_functions_validation import validate_http\n"
                "app=func.FunctionApp()\n@app.route(route='hello')\ndef hello(req): return 'ok'\n"
            )
        (project / "requirements.txt").write_text(requirements)
        if fixture == "root-symlink":
            (project / "requirements.txt").rename(project / "root-manifest.txt")
            (project / "requirements.txt").symlink_to(project / "root-manifest.txt")
    (project / "pyproject.toml").write_text('[project]\nname="fixture"\ndependencies=[]\n')
    (project / "main.bicep").write_text("linuxFxVersion: 'Python|3.12'\n")
    if fixture in {"alias-base", "alias-integration", "alias-gap"}:
        (project / "sub").mkdir()
        (project / "sub/manifest.txt").write_text("-r common.txt\n")
        (project / "requirements.txt").unlink()
        (project / "requirements.txt").symlink_to(project / "sub/manifest.txt")
        (project / "common.txt").write_text("azure-functions==1.21.3\nnumpy\n")
        (project / "sub/common.txt").write_text("azure-functions-worker\n")
        if fixture == "alias-integration":
            (project / "common.txt").write_text(
                "azure-functions==1.21.3\nazure-functions-validation\nazure-functions-openapi\n"
            )
            (project / "sub/common.txt").write_text("azure-functions-validation\n")
        elif fixture == "alias-gap":
            (project / "sub/manifest.txt").write_text("-r ../common.txt\n")
    elif fixture == "bom-include":
        (project / "requirements.txt").write_bytes(b"\xef\xbb\xbf-r child.txt\n")
        (project / "child.txt").write_text("azure-functions==1.21.3\n")
    elif fixture == "included-alias-base":
        (project / "sub").mkdir()
        (project / "requirements.txt").write_text("azure-functions==1.21.3\n-r alias.txt\n")
        (project / "alias.txt").symlink_to(project / "sub/manifest.txt")
        (project / "sub/manifest.txt").write_text("-r common.txt\n")
        (project / "common.txt").write_text("azure-functions-worker\n")
        (project / "sub/common.txt").write_text("numpy\nazure-functions-validation\n")
    elif fixture == "bom-child":
        (project / "requirements.txt").write_text("azure-functions==1.21.3\n-r child.txt\n")
        (project / "child.txt").write_bytes(b"\xef\xbb\xbf-r common.txt\n")
        (project / "common.txt").write_text("numpy\n")
    elif fixture == "crlf":
        (project / "requirements.txt").write_bytes(b"azure-functions==1.21.3\r\n-r child.txt\r\n")
        (project / "child.txt").write_bytes(b"numpy\r\nrequests==2.32.5\r")
    elif fixture == "bom-funcignore":
        (project / ".funcignore").write_bytes(b"\xef\xbb\xbf.venv\n")
        (project / ".venv").mkdir()
        (project / ".venv/hello").touch()
    if fixture == "deploy":
        (project / "infra.json").write_text(
            '{"functionAppConfig":{"runtime":{"name":"python","version":"3.12"},'
            '"deployment":{"storage":{"type":"blobContainer","value":"https://example.invalid",'
            '"authentication":{"type":"SystemAssignedIdentity"}}}}}'
        )
    env = {
        "PYTHONPATH": os.environ.get("DOCTOR_GOLDEN_SOURCE", str(Path("src").absolute())),
        "PATH": str(tmp_path / "empty-bin"),
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONHASHSEED": "0",
        "COLUMNS": "10000",
        "LINES": "40",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    # When the real CLI renders each format in an isolated interpreter.
    run = subprocess.run(
        [sys.executable, "-c", PROBE, str(project), output_format],
        env=env,
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(run.stdout)
    payload["output"] = payload["output"].replace(str(project), "<PROJECT>")
    payload["output"] = payload["output"].replace(sys.executable, "<PYTHON_EXECUTABLE>")
    payload["output"] = re.sub(
        r'("generated_at": ")[^"]+("|$)', r"\1<TIMESTAMP>\2", payload["output"]
    )
    payload["output"] = re.sub(
        r"Tool runtime: \d+\.\d+\.\d+", "Tool runtime: <PYTHON>", payload["output"]
    )
    payload["output"] = re.sub(
        r'("(?:tool_version|python_version)": ")[^"]+("|$)',
        r"\1<VERSION>\2",
        payload["output"],
    )
    saved = BASELINES / f"{fixture}-{output_format}.json"
    if os.environ.get("DOCTOR_GOLDEN_RECORD") == "1":
        saved.write_text(json.dumps(payload, indent=2) + "\n")
    # Then bytes and exit codes equal the baseline, not a recomputed main import.
    expected = json.loads(saved.read_text())
    assert payload["code"] == expected["code"]
    assert payload["output"] == expected["output"], "\n".join(
        difflib.unified_diff(expected["output"].splitlines(), payload["output"].splitlines())
    )
