"""Deterministic filesystem escape probes; never touch host secrets."""

import os
from pathlib import Path

import pytest

from azure_functions_doctor.deploy_config import local_settings_values
from azure_functions_doctor.handlers._helpers import (
    _iter_requirements_txt_lines,
    _read_project_python_file,
    iter_project_files,
)
from azure_functions_doctor.inspection import read_inspection_text


@pytest.mark.parametrize("reference", ["../outside.txt", "absolute", "../nested/../outside.txt"])
def test_requirements_includes_stay_inside_selected_root(tmp_path: Path, reference: str) -> None:
    # Given a project referencing a sibling file outside its selected root.
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("CANARY_SECRET_OUTSIDE\n", encoding="utf-8")
    if reference == "absolute":
        reference = str(outside)
    # When includes are inspected, never interpreted by pip.
    lines = _iter_requirements_txt_lines(f"-r {reference}\n", root / "requirements.txt")
    # Then no out-of-root content enters diagnostics.
    assert "CANARY_SECRET_OUTSIDE" not in repr(lines)


def test_traversal_skips_outside_symlink_when_project_contains_link(tmp_path: Path) -> None:
    # Given a link to a synthetic file outside the root and a parent-directory loop.
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("raise RuntimeError('CANARY_SECRET_OUTSIDE')", encoding="utf-8")
    (root / "escape.py").symlink_to(outside)
    (root / "parent").symlink_to(tmp_path, target_is_directory=True)
    # When discovering source files.
    files = list(iter_project_files(root, "*.py"))
    # Then no outside file is offered to readers and the loop terminates.
    assert files == []


def test_local_settings_symlink_cannot_read_outside_root(tmp_path: Path) -> None:
    # Given a direct configuration filename linked outside the selected root.
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"Values":{"Secret":"CANARY_SECRET_OUTSIDE"}}', encoding="utf-8")
    (root / "local.settings.json").symlink_to(outside)
    # When deployment settings are ingested; Then no outside content is returned.
    assert local_settings_values(root) == {}


def test_source_read_is_bounded_when_file_is_large(tmp_path: Path) -> None:
    # Given a sparse source file larger than the documented inspection limit.
    source = tmp_path / "large.py"
    with source.open("wb") as stream:
        stream.truncate(8 * 1024 * 1024)
    # When inspecting source; Then the oversized file is skipped rather than loaded.
    assert _read_project_python_file(source) is None


def test_shared_reader_skips_fifo_without_blocking(tmp_path: Path) -> None:
    # Given a FIFO disguised as source; When inspected; Then it is rejected before reading.
    fifo = tmp_path / "pipe.py"
    os.mkfifo(fifo)
    with pytest.raises(OSError, match="regular file"):
        read_inspection_text(fifo)


def test_shared_reader_rejects_invalid_utf8(tmp_path: Path) -> None:
    # Given invalid UTF-8; When read at the strict boundary; Then decoding fails safely.
    source = tmp_path / "invalid.json"
    source.write_bytes(b"\xff\xfeCANARY_SECRET")
    with pytest.raises(UnicodeDecodeError):
        read_inspection_text(source)


@pytest.mark.parametrize("reference", [r"..\outside.txt", r"C:\outside.txt"])
def test_windows_reference_cannot_escape_manifest(tmp_path: Path, reference: str) -> None:
    # Given Windows-style out-of-root syntax; When includes resolve; Then nothing is read.
    assert _iter_requirements_txt_lines(f"-r {reference}\n", tmp_path / "requirements.txt") == []


def test_source_read_skips_binary_when_file_has_nul(tmp_path: Path) -> None:
    # Given binary content disguised as Python source.
    source = tmp_path / "binary.py"
    source.write_bytes(b"app = func.FunctionApp()\x00CANARY_SECRET_BINARY")
    # When inspecting source; Then it is not parsed as application code.
    assert _read_project_python_file(source) is None
