import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.target_resolver import resolve_target_value


@pytest.mark.parametrize("suffix", ["; touch PWNED", "$(touch PWNED)", "`touch PWNED`"])
def test_git_keeps_injection_in_one_argument(tmp_path: Path, suffix: str) -> None:
    # Given shell syntax in a project directory containing local settings.
    root = tmp_path / suffix
    root.mkdir()
    (root / "local.settings.json").write_text('{"Values":{}}', encoding="utf-8")
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1)) as spy:
        # When the tracking check queries git metadata.
        result = HandlerRegistry().handle({"type": "local_settings_security"}, root)
    # Then the path is one argv element, no shell is invoked, and execution is timed.
    args, kwargs = spy.call_args
    assert args[0][0] == "git"
    assert str(root) in args[0]
    assert kwargs.get("shell", False) is False
    assert kwargs["timeout"] == 10
    assert "core.fsmonitor=false" in args[0]
    assert result["status"] == "pass"
    assert not (tmp_path / "PWNED").exists()


def test_static_inspection_never_executes_project_metadata(tmp_path: Path) -> None:
    # Given executable-looking Python metadata and application code.
    marker = tmp_path / "PWNED"
    (tmp_path / "setup.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n", encoding="utf-8"
    )
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="$(touch PWNED)"\ndependencies=["azure-functions"]\n', encoding="utf-8"
    )
    with patch("subprocess.run") as run, patch("subprocess.Popen") as popen:
        # When only static minimal diagnostics execute.
        results = Doctor(str(tmp_path), profile="minimal").run_all_checks()
    # Then neither project code nor a project-provided command is executed.
    run.assert_not_called()
    popen.assert_not_called()
    assert not marker.exists()
    assert "check_azure_functions_library" in json.dumps(results)


def test_core_tools_exception_does_not_log_credentials(caplog: pytest.LogCaptureFixture) -> None:
    # Given a failing executable whose exception message contains a credential.
    with (
        patch("shutil.which", return_value="/trusted/func"),
        patch(
            "azure_functions_doctor.target_resolver.read_tool_output",
            side_effect=RuntimeError("Bearer CANARY_SECRET_COMMAND"),
        ),
    ):
        # When the resolver handles that failure.
        result = resolve_target_value("func_core_tools")
    # Then status remains useful without the raw exception payload.
    assert result == "unknown_error"
    assert "CANARY_SECRET_COMMAND" not in caplog.text
