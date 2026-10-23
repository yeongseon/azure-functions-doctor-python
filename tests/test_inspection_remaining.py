"""Remaining #622 readers: regressions against main 94f987f."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Literal

import pytest

from azure_functions_doctor import inspection
from azure_functions_doctor.agent import AgentReportError, load_agent_report
from azure_functions_doctor.deploy_config import flex_deployment_storage_shape
from azure_functions_doctor.handlers._helpers import (
    _iter_requirements_txt_lines,
    _load_pyproject,
    _read_project_python_file,
)
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps
from azure_functions_doctor.target_resolver import _resolve_func_core_tools


@pytest.mark.parametrize(
    "kind", ["dev_storage_connection", "linux_fx_version", "host_json_version"]
)
def test_rule_refuses_oversized_file_visibly(
    tmp_path: Path,
    kind: Literal["dev_storage_connection", "linux_fx_version", "host_json_version"],
) -> None:
    # Given an oversized, otherwise readable inspected file.
    target = tmp_path / ("host.json" if kind == "host_json_version" else "main.bicep")
    target.write_text(" " * (inspection.MAX_FILE_BYTES + 1))
    # When the real rule runs.
    result = HandlerRegistry().handle({"type": kind}, tmp_path)
    # Then refusal is visible rather than a clean pass/skip.
    assert "not inspected" in result["detail"]


def test_flex_json_reader_refuses_symlink(tmp_path: Path) -> None:
    # Given deployable JSON linked to a file outside the selected root.
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"deployment":{"storage":{"value":"CANARY"}}}')
    (root / "infra.json").symlink_to(outside)
    # When resolving storage; Then outside content cannot be ingested.
    assert flex_deployment_storage_shape(root) is None


def test_toml_reader_refuses_oversized_file(tmp_path: Path) -> None:
    # Given a valid oversized manifest.
    (tmp_path / "pyproject.toml").write_text("#" + "x" * inspection.MAX_FILE_BYTES)
    # When loading it; Then the inspection boundary refuses it.
    assert _load_pyproject(tmp_path) is None


def test_invalid_utf8_source_has_no_unbounded_fallback(tmp_path: Path) -> None:
    # Given undecodable source which previously bypassed the shared reader.
    source = tmp_path / "app.py"
    source.write_bytes(b"\xffapp = func.FunctionApp()")
    # When reading it; Then it is visibly refused, not decoded with errors ignored.
    with collect_inspection_gaps() as gaps:
        assert _read_project_python_file(source) is None
    assert gaps


def test_json_guard_is_string_aware_and_linear(tmp_path: Path) -> None:
    # Given deep JSON and a large unterminated escaped string (quadratic-regex trap).
    target = tmp_path / "host.json"
    target.write_text("[" * 101 + "0" + "]" * 101)
    reader = getattr(inspection, "read_inspection_json", None)
    assert reader is not None
    # When parsing hostile input; Then depth is refused before json.loads.
    with pytest.raises(OSError):
        reader(target)
    target.write_text('"' + '\\"' * 100_000)
    start = time.monotonic()
    with pytest.raises(json.JSONDecodeError):
        reader(target)
    assert time.monotonic() - start < 2
    target.write_text(json.dumps({"brackets": "[" * 101, "escaped": '\\"'}))
    assert reader(target) == {"brackets": "[" * 101, "escaped": '\\"'}


def test_agent_error_does_not_echo_parser_token(tmp_path: Path) -> None:
    # Given an invalid JSON escape whose parser text echoes a credential-like token.
    target = tmp_path / "report.json"
    target.write_text('{"x":"\\uCANARY_SECRET_TOKEN"}')
    # When the adapter reports failure; Then only the exception type is exposed.
    with pytest.raises(AgentReportError) as error:
        load_agent_report(target)
    assert "CANARY_SECRET_TOKEN" not in str(error.value)
    assert "JSONDecodeError" in str(error.value)


def test_include_file_cap_is_visible(tmp_path: Path) -> None:
    # Given many distinct includes, each individually within the byte limit.
    content = "".join(f"-r req-{i}.txt\n" for i in range(130))
    for i in range(130):
        (tmp_path / f"req-{i}.txt").write_text("azure-functions\n")
    # When traversing; Then cumulative work is bounded and refusal is visible.
    with collect_inspection_gaps() as gaps:
        _iter_requirements_txt_lines(content, tmp_path / "requirements.txt")
    assert gaps


def test_func_output_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given a fake executable emitting far more output than a version requires.
    executable = tmp_path / "func"
    executable.write_text(f"#!{sys.executable}\nimport sys\nsys.stdout.write('9' * 200000)\n")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    # When probing Core Tools; Then oversized output is refused.
    result = _resolve_func_core_tools()
    assert len(result) < 100


def test_git_probe_discards_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given git's tracking check needs only its return code, not either stream.
    (tmp_path / "local.settings.json").write_text("{}")
    original = subprocess.run

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert kwargs.get("stdout") == subprocess.DEVNULL
        assert kwargs.get("stderr") == subprocess.DEVNULL
        return subprocess.CompletedProcess(["git"], 1)

    monkeypatch.setattr(subprocess, "run", run)
    # When the tracking rule runs; Then capture is disabled at the process boundary.
    result = HandlerRegistry().handle({"type": "local_settings_security"}, tmp_path)
    monkeypatch.setattr(subprocess, "run", original)
    assert result["status"] == "pass"
