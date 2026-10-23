from pathlib import Path
from typing import Literal

import pytest

from azure_functions_doctor.agent import AgentReportError, load_agent_report
from azure_functions_doctor.deploy_config import _read_text
from azure_functions_doctor.handlers._helpers import _load_pyproject, _read_project_python_file
from azure_functions_doctor.inspection import read_inspection_text
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps
from azure_functions_doctor.requirements_inspection import read_requirements_text


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
@pytest.mark.parametrize("universal", [True, False])
def test_bounded_reader_preserves_explicit_decoding_and_newline_contract(
    tmp_path: Path, encoding: Literal["utf-8", "utf-8-sig"], universal: bool
) -> None:
    target = tmp_path / "text"
    target.write_bytes(b"\xef\xbb\xbffirst\r\nsecond\rthird\n")
    expected = "first\r\nsecond\rthird\n"
    if encoding == "utf-8":
        expected = "\ufeff" + expected
    if universal:
        expected = expected.replace("\r\n", "\n").replace("\r", "\n")
    assert read_inspection_text(target, encoding=encoding, universal_newlines=universal) == expected


@pytest.mark.parametrize("kind", ["source", "deploy"])
def test_preexisting_binary_backed_readers_preserve_raw_newlines(tmp_path: Path, kind: str) -> None:
    target = tmp_path / ("app.py" if kind == "source" else "main.bicep")
    target.write_bytes(b"\xef\xbb\xbfx=1\r\ny=2\rz=3\n")
    text = _read_project_python_file(target) if kind == "source" else _read_text(target)
    assert text == "x=1\r\ny=2\rz=3\n"


def test_package_requirements_reader_retains_bom_and_normalizes_newlines(tmp_path: Path) -> None:
    target = tmp_path / "requirements.txt"
    target.write_bytes(b"\xef\xbb\xbf-r child.txt\r\n")
    assert read_requirements_text(target, tmp_path, encoding="utf-8") == "\ufeff-r child.txt\n"


def test_binary_toml_loading_does_not_accept_lone_cr_as_a_newline(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_bytes(b'[project]\rname="fixture"\r')
    with collect_inspection_gaps() as gaps:
        assert _load_pyproject(tmp_path) is None
    assert gaps


def test_agent_preserves_utf8_bom_rejection(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_bytes(b'\xef\xbb\xbf{"schema_version":"2.0","results":[]}')
    with pytest.raises(AgentReportError):
        load_agent_report(report)
