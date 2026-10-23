"""Canaries at diagnostic output boundaries; filenames remain visible metadata."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.agent import AgentReportError, load_agent_report
from azure_functions_doctor.cli import cli
from azure_functions_doctor.handlers._helpers import _load_pyproject

CANARY = "CANARY_SECRET_TOKEN_622"


@pytest.mark.parametrize("output_format", ["table", "json", "sarif", "junit"])
def test_malformed_project_keeps_content_out_of_outputs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, output_format: str
) -> None:
    # Given real malformed project content, including a TOML error echoing a token.
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp=func.FunctionApp()"
    )
    (tmp_path / "host.json").write_text('{"version":"2.0","x":"\\u' + CANARY + '"}')
    (tmp_path / "pyproject.toml").write_text(f"{CANARY} = 1\n{CANARY} = 2\n")
    (tmp_path / "requirements.txt").write_text("azure-functions==1.21.3\n")
    summary = tmp_path / "summary.json"
    report = tmp_path / "report"
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    logging.getLogger("azure_functions_doctor").handlers.clear()
    # When every public serializer runs and a sidecar is written.
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
    # Then file contents never reach reports, terminal or DEBUG logs.
    assert result.exit_code in (0, 1)
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert CANARY not in result.output + report.read_text() + summary.read_text() + caplog.text
    if output_format == "json":
        assert CANARY not in repr(load_agent_report(report))


def test_write_failures_hide_exception_and_filename_canaries(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Given a write error containing a credential and credential-looking destination.
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    logging.getLogger("azure_functions_doctor").handlers.clear()
    destination = tmp_path / CANARY
    with patch.object(Path, "write_text", side_effect=PermissionError(CANARY)):
        # When report and summary writes fail; Then diagnostics expose type only.
        result = CliRunner().invoke(
            cli,
            [
                "doctor",
                "--path",
                str(tmp_path),
                "--format",
                "json",
                "--output",
                str(destination),
                "--summary-json",
                str(destination),
            ],
        )
    assert result.exit_code == 1
    assert CANARY not in result.output + caplog.text


def test_toml_debug_error_hides_duplicate_key_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Given a duplicate key echoed by TOMLDecodeError's message.
    (tmp_path / "pyproject.toml").write_text(f"{CANARY}=1\n{CANARY}=2")
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    # When the manifest loader logs the failure; Then content is not logged.
    assert _load_pyproject(tmp_path) is None
    assert CANARY not in caplog.text


def test_agent_error_hides_filename_canary(tmp_path: Path) -> None:
    # Given a malformed report in a credential-looking filename.
    report = tmp_path / CANARY
    report.write_text("not JSON")
    # When loading it; Then exception text does not repeat the filename or input.
    with pytest.raises(AgentReportError) as error:
        load_agent_report(report)
    assert CANARY not in str(error.value)
