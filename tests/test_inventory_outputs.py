import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.agent import load_agent_report
from azure_functions_doctor.cli import cli
from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers._helpers import _handle_exception
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.logging_config import log_diagnostic_start, log_rule_execution
from azure_functions_doctor.target_resolver import _resolve_func_core_tools


def test_inventory_func_output_is_bounded_at_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "func"
    executable.write_text(f"#!{sys.executable}\nimport sys\nsys.stdout.write('9'*200000)\n")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert len(_resolve_func_core_tools()) < 100


def test_inventory_git_probe_does_not_capture_streams(tmp_path: Path) -> None:
    (tmp_path / "local.settings.json").write_text("{}")
    with patch.object(
        subprocess, "run", return_value=subprocess.CompletedProcess(["git"], 1)
    ) as run:
        result = HandlerRegistry().handle({"type": "local_settings_security"}, tmp_path)
    assert result["status"] == "pass"
    assert run.call_args.kwargs["stdout"] == subprocess.DEVNULL
    assert run.call_args.kwargs["stderr"] == subprocess.DEVNULL


@pytest.mark.parametrize("output_format", ["table", "json", "sarif", "junit"])
def test_inventory_exception_result_remains_secret_free_across_serializers(
    tmp_path: Path, output_format: str, caplog: pytest.LogCaptureFixture
) -> None:
    token = "CANARY_SERIALIZER_SECRET"
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp=func.FunctionApp()"
    )
    report = tmp_path / "report"
    summary = tmp_path / "summary.json"
    logging.getLogger("azure_functions_doctor").handlers.clear()
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    handler_result = _handle_exception("reading project", ValueError(token))
    with patch("azure_functions_doctor.doctor.generic_handler", return_value=handler_result):
        result = CliRunner().invoke(
            cli,
            [
                "doctor",
                "--path",
                str(tmp_path),
                "--format",
                output_format,
                "--output",
                str(report),
                "--summary-json",
                str(summary),
            ],
        )
    assert result.exit_code == 1
    assert token not in result.output + report.read_text() + summary.read_text() + caplog.text
    if output_format == "json":
        assert token not in repr(load_agent_report(report))


@pytest.mark.parametrize("destination", ["output", "summary-json"])
def test_inventory_write_failure_logs_omit_payload(
    tmp_path: Path, destination: str, caplog: pytest.LogCaptureFixture
) -> None:
    token = "CANARY_WRITE_SECRET"
    logging.getLogger("azure_functions_doctor").handlers.clear()
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    with patch.object(Path, "write_text", side_effect=PermissionError(token)):
        result = CliRunner().invoke(
            cli,
            [
                "doctor",
                "--path",
                str(tmp_path),
                "--format",
                "json",
                "--" + destination,
                str(tmp_path / token),
            ],
        )
    assert token not in result.output + caplog.text


def test_inventory_logging_preserves_metadata_but_escapes_controls(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("azure_functions_doctor")
    logger.handlers.clear()
    logger.propagate = True
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    log_diagnostic_start("CANARY_FILENAME\x1b[31m", 1)
    log_rule_execution("rule", "file_exists", "pass", 1)
    assert "CANARY_FILENAME" in caplog.text
    assert "\x1b" not in caplog.text
    assert "\\u001b" in caplog.text


def test_inventory_logging_does_not_invent_secret_setting_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("azure_functions_doctor")
    logger.handlers.clear()
    logger.propagate = True
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    with patch.dict(os.environ, {"UNKNOWN_SECRET_SETTING": "CANARY_VALUE_SECRET"}):
        log_diagnostic_start("CANARY_FILENAME", 1)
        log_rule_execution("rule", "file_exists", "pass", 1)
    assert "CANARY_FILENAME" in caplog.text
    assert "CANARY_VALUE_SECRET" not in caplog.text


def test_inventory_publish_tag_cannot_execute_shell_substitution(tmp_path: Path) -> None:
    workflow = Path(".github/workflows/publish-pypi.yml").read_text()
    block = workflow.split("      - name: Check if tag matches __version__\n", 1)[1]
    script = block.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
    script = "\n".join(line[10:] for line in script.splitlines())
    marker = tmp_path / "injected"
    tag = f"$(touch {marker})"
    script = script.replace("${{ github.ref_name }}", tag)
    env = {**os.environ, "TAG_NAME": tag, "GITHUB_OUTPUT": str(tmp_path / "outputs")}
    subprocess.run(["bash", "-c", script], env=env, capture_output=True, timeout=10)
    assert not marker.exists()


def test_inventory_bundled_asset_rules_are_not_project_files(tmp_path: Path) -> None:
    (tmp_path / "v2.json").write_text("CANARY_PROJECT_RULE")
    assert "CANARY_PROJECT_RULE" not in json.dumps(Doctor(str(tmp_path)).load_rules())
