from pathlib import Path
import subprocess
import sys
from typing import Optional

import pytest

from azure_functions_doctor import target_resolver


def test_resolve_python_version() -> None:
    """Test resolving the current Python version."""
    result = target_resolver.resolve_target_value("python")
    assert result == sys.version.split()[0]


def test_resolve_python_version_override() -> None:
    """Test resolving an overridden Python target version."""
    result = target_resolver.resolve_target_value("python", override="3.12")
    assert result == "3.12"


def test_resolve_func_core_tools_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolving func_core_tools version via subprocess."""
    monkeypatch.setattr(
        "azure_functions_doctor.target_resolver.shutil.which", lambda name: "/usr/bin/func"
    )

    def mock_check_output(cmd: list[str], text: bool, timeout: Optional[int] = None) -> str:
        return "4.0.5198"

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    result = target_resolver.resolve_target_value("func_core_tools")
    assert result == "4.0.5198"


def test_resolve_func_core_tools_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback when func_core_tools resolution fails."""
    monkeypatch.setattr(
        "azure_functions_doctor.target_resolver.shutil.which", lambda name: "/usr/bin/func"
    )

    def mock_check_output(cmd: list[str], text: bool, timeout: Optional[int] = None) -> str:
        raise Exception("not found")

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    result = target_resolver.resolve_target_value("func_core_tools")
    assert result == "unknown_error"


def test_resolve_func_core_tools_not_installed_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("azure_functions_doctor.target_resolver.shutil.which", lambda name: None)

    result = target_resolver.resolve_target_value("func_core_tools")

    assert result == "not_installed"


def test_resolve_func_core_tools_timeout_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "azure_functions_doctor.target_resolver.shutil.which", lambda name: "/usr/bin/func"
    )

    def mock_check_output(cmd: list[str], text: bool, timeout: Optional[int] = None) -> str:
        raise subprocess.TimeoutExpired(cmd, 10.0)

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    result = target_resolver.resolve_target_value("func_core_tools")
    assert result == "timeout"


def test_resolve_func_core_tools_called_process_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "azure_functions_doctor.target_resolver.shutil.which", lambda name: "/usr/bin/func"
    )

    def mock_check_output(cmd: list[str], text: bool, timeout: Optional[int] = None) -> str:
        raise subprocess.CalledProcessError(2, cmd)

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    result = target_resolver.resolve_target_value("func_core_tools")
    assert result == "error_2"


def test_resolve_python_target_override_short_circuits(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10"\n', encoding="utf-8"
    )
    version, source = target_resolver.resolve_python_target(tmp_path, override="3.12")
    assert (version, source) == ("3.12", "override")


def test_resolve_python_target_ignores_pyproject_requires_python(tmp_path: Path) -> None:
    """``requires-python`` is a floor, not a target, so it must be ignored."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nrequires-python = ">=3.11,<3.15"\n', encoding="utf-8"
    )
    version, source = target_resolver.resolve_python_target(tmp_path)
    assert (version, source) == (sys.version.split()[0], "tool-runtime")


def test_resolve_python_target_from_python_version_file(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12.4\n", encoding="utf-8")
    version, source = target_resolver.resolve_python_target(tmp_path)
    assert (version, source) == ("3.12.4", ".python-version")


def test_resolve_python_target_python_version_precedes_pyproject(tmp_path: Path) -> None:
    """.python-version wins; pyproject requires-python is never a target."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.10"\n', encoding="utf-8"
    )
    (tmp_path / ".python-version").write_text("3.13\n", encoding="utf-8")
    version, source = target_resolver.resolve_python_target(tmp_path)
    assert (version, source) == ("3.13", ".python-version")


def test_resolve_python_target_pyproject_without_requires_python(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (tmp_path / ".python-version").write_text("3.13\n", encoding="utf-8")
    version, source = target_resolver.resolve_python_target(tmp_path)
    assert (version, source) == ("3.13", ".python-version")


def test_resolve_python_target_ignores_unparseable_python_version(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("not-a-version\n", encoding="utf-8")
    version, source = target_resolver.resolve_python_target(tmp_path)
    assert (version, source) == (sys.version.split()[0], "tool-runtime")


def test_resolve_python_target_falls_back_to_tool_runtime(tmp_path: Path) -> None:
    version, source = target_resolver.resolve_python_target(tmp_path)
    assert (version, source) == (sys.version.split()[0], "tool-runtime")


def test_resolve_python_target_no_project_path(tmp_path: Path) -> None:
    version, source = target_resolver.resolve_python_target(None)
    assert (version, source) == (sys.version.split()[0], "tool-runtime")


@pytest.mark.parametrize(
    "version, expected",
    [
        ("3.10", True),
        ("3.11", True),
        ("3.12", True),
        ("3.13", True),
        ("3.14", True),
        ("3.14.7", True),
        ("3.12.4", True),
        ("3.9", False),
        ("3.9.18", False),
        ("3.15", False),
        ("3.15.0", False),
        ("2.7", False),
        ("not-a-version", False),
    ],
)
def test_is_supported_python_target(version: str, expected: bool) -> None:
    assert target_resolver.is_supported_python_target(version) is expected
