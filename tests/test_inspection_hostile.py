import ast
import os
from pathlib import Path
import subprocess
import sys
from typing import Literal

import pytest

from azure_functions_doctor.handlers._helpers import _read_project_python_file
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.inspection import read_inspection_toml
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps
from azure_functions_doctor.process_inspection import read_tool_output
from azure_functions_doctor.requirements_inspection import iter_requirements_files


@pytest.mark.parametrize("failure", [RecursionError, MemoryError, ValueError])
def test_python_parser_resource_failure_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: type[Exception]
) -> None:
    # Given a file whose parser hits a resource/invalid-source failure.
    source = tmp_path / "function_app.py"
    source.write_text("app = func.FunctionApp()")

    def parse(source: str) -> ast.Module:
        raise failure("CANARY_SECRET_PARSER")

    monkeypatch.setattr(ast, "parse", parse)
    # When reading source; Then refusal is visible without a traceback or payload.
    with collect_inspection_gaps() as gaps:
        assert _read_project_python_file(source) is None
    assert gaps


@pytest.mark.parametrize("kind", ["package_declared", "package_forbidden"])
@pytest.mark.parametrize("reference", ["absolute", "../outside.txt"])
def test_configured_requirements_cannot_escape_root(
    tmp_path: Path,
    kind: Literal["package_declared", "package_forbidden"],
    reference: str,
) -> None:
    # Given a rule-configured manifest outside the project root.
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("CANARY_SECRET_REQUIREMENT")
    if reference == "absolute":
        reference = str(outside)
    # When either consumer runs; Then no content is read and refusal is visible.
    result = HandlerRegistry().handle(
        {"type": kind, "condition": {"package": "azure-functions", "file": reference}}, root
    )
    assert "not inspected" in result["detail"]
    assert "CANARY_SECRET_REQUIREMENT" not in repr(result)


@pytest.mark.parametrize("kind", ["fifo", "symlink", "binary", "deep-json"])
def test_hostile_host_file_is_refused(tmp_path: Path, kind: str) -> None:
    # Given hostile host metadata presented to the real rule dispatcher.
    host = tmp_path / "host.json"
    if kind == "fifo":
        os.mkfifo(host)
    elif kind == "symlink":
        outside = tmp_path / "outside"
        outside.write_text('{"version":"2.0"}')
        host.symlink_to(outside)
    elif kind == "binary":
        host.write_bytes(b"\x00CANARY_SECRET")
    else:
        host.write_text("[" * 10000 + "0" + "]" * 10000)
    # When host version is checked; Then failure is visible and bounded.
    result = HandlerRegistry().handle({"type": "host_json_version"}, tmp_path)
    assert "not inspected" in result["detail"]


def test_requirements_byte_budget_and_cycles(tmp_path: Path) -> None:
    # Given a cyclic include graph whose distinct files exceed the byte budget.
    root = tmp_path / "requirements.txt"
    root.write_text("-r req0.txt\n")
    for i in range(6):
        (tmp_path / f"req{i}.txt").write_text(
            "#" + "x" * (3 * 1024 * 1024) + f"\n-r req{i + 1}.txt\n-r requirements.txt\n"
        )
    # When traversal runs; Then cumulative work stops with evidence.
    with collect_inspection_gaps() as gaps:
        files = list(iter_requirements_files(root))
    assert len(files) <= 6
    assert gaps


def test_requirements_depth_budget(tmp_path: Path) -> None:
    # Given a deep local chain.
    for i in range(12):
        (tmp_path / f"req{i}.txt").write_text(f"-r req{i + 1}.txt\n")
    # When traversal runs; Then the depth cap is visible.
    with collect_inspection_gaps() as gaps:
        files = list(iter_requirements_files(tmp_path / "req0.txt"))
    assert len(files) == 10
    assert gaps


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_fake_tool_large_streams_do_not_accumulate(tmp_path: Path, stream: str) -> None:
    # Given an executable producing 16 MiB on either stream.
    script = tmp_path / "tool.py"
    script.write_text(f"import sys\nsys.{stream}.write('x' * (16 * 1024 * 1024))\n")
    # When capturing version output; Then stdout is refused and stderr is discarded.
    if stream == "stdout":
        with pytest.raises(OSError, match="oversized"):
            read_tool_output([sys.executable, str(script)])
    else:
        assert read_tool_output([sys.executable, str(script)]) == ""


def test_tool_timeout_reaps_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given an installed-tool stand-in that never completes.
    script = tmp_path / "tool.py"
    script.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr("azure_functions_doctor.process_inspection.PROCESS_TIMEOUT_SECONDS", 0.1)
    # When the deadline expires; Then the child is killed and reaped before returning.
    with pytest.raises(subprocess.TimeoutExpired):
        read_tool_output([sys.executable, str(script)])


@pytest.mark.skipif(os.name != "posix", reason="POSIX inherited-pipe/process-group probe")
def test_tool_descendant_cannot_hold_pipe_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a child inheriting stdout after its parent exits.
    script = tmp_path / "tool.py"
    script.write_text(
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    )
    monkeypatch.setattr("azure_functions_doctor.process_inspection.PROCESS_TIMEOUT_SECONDS", 0.1)
    # When capture times out; Then the process group cannot retain the pipe indefinitely.
    with pytest.raises(subprocess.TimeoutExpired):
        read_tool_output([sys.executable, str(script)])


def test_toml_duplicate_key_is_graceful(tmp_path: Path) -> None:
    # Given duplicate keys that echo content in stdlib parser messages.
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("CANARY_TOKEN=1\nCANARY_TOKEN=2")
    # When bounded parsing fails; Then payload text does not escape.
    with pytest.raises(OSError) as error:
        read_inspection_toml(manifest)
    assert "CANARY_TOKEN" not in str(error.value)
