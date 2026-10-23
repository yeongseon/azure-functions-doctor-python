"""Review regressions at the actual diagnostic rule boundary."""

import os
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest

from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.inspection import read_inspection_text


@pytest.mark.parametrize("kind", ["native_dependency_risk", "unpinned_requirements"])
@pytest.mark.parametrize(
    "include",
    [
        "-r ../outside.txt",
        "--requirement=../outside.txt",
        "-c ../outside.txt",
        "--constraint=../outside.txt",
        "absolute",
    ],
)
def test_rule_ignores_requirements_outside_manifest(
    tmp_path: Path, kind: Literal["native_dependency_risk", "unpinned_requirements"], include: str
) -> None:
    # Given an outside unpinned native dependency referenced by the manifest.
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("numpy\n")
    if include == "absolute":
        include = f"-r {tmp_path / 'outside.txt'}"
    (root / "requirements.txt").write_text(include + "\n")
    # When either consumer evaluates its rule.
    result = HandlerRegistry().handle(
        {"type": "native_dependency_risk"}
        if kind == "native_dependency_risk"
        else {"type": "unpinned_requirements"},
        root,
    )
    # Then the outside declaration never enters findings.
    assert result["status"] == "fail"
    assert result["severity"] == "warning"
    assert result["gate"] is False
    assert result["file"] == "requirements.txt"
    assert result["line"] == 1
    assert "not inspected" in result["detail"]
    assert "--path" in result["detail"]
    assert "numpy" not in result["detail"]


def test_reader_and_model_detection_work_without_unix_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a normal v2 source on a platform without Unix-only open flags.
    source = tmp_path / "function_app.py"
    source.write_text("import azure.functions as func\napp = func.FunctionApp()\n")
    monkeypatch.delattr(os, "O_NONBLOCK", raising=False)
    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
    # When reading source and constructing the public diagnostic runner.
    assert "FunctionApp" in read_inspection_text(source)
    doctor = Doctor(str(tmp_path))
    # Then programming-model discovery does not abort.
    assert doctor is not None


def test_known_fifo_is_not_opened_without_nonblocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a known nonregular source and no platform nonblocking support.
    fifo = tmp_path / "pipe.py"
    os.mkfifo(fifo)
    monkeypatch.delattr(os, "O_NONBLOCK", raising=False)
    # When inspecting it; Then rejection happens before opening the FIFO.
    with patch("os.open", side_effect=AssertionError("must not open FIFO")):
        with pytest.raises(OSError, match="regular file"):
            read_inspection_text(fifo)
