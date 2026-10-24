"""Repository ``make`` prerequisites: ``doctor`` reports missing tools, ``bootstrap`` is idempotent.

``make doctor`` checks the repository's own prerequisites. It is not the product CLI
(``azure-functions-doctor doctor``). Each test runs ``make`` on a scratch copy of the Makefile
with ``PATH`` limited to a stub directory, plus a stub ``pip`` in the scratch virtual
environment, so nothing is installed and no network is used.
"""

from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKE = shutil.which("make") or "make"
REQUIRED = ("hatch", "python3.11", "git")
OPTIONAL = ("func", "azurite")


def _stub(path: Path, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}exit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _pip_log(sandbox: Path) -> Path:
    """Put a stub ``pip`` in the scratch venv; it appends its arguments to the returned file."""
    log = sandbox / "pip.log"
    _stub(sandbox / "venv/bin/pip", f'echo "$*" >> {shlex.quote(str(log))}\n')
    return log


def _install_tools(sandbox: Path, missing: set[str]) -> None:
    for tool in (*REQUIRED, *OPTIONAL):
        if tool not in missing:
            _stub(sandbox / ("venv/bin" if tool == "hatch" else "bin") / tool)


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    shutil.copy(ROOT / "Makefile", tmp_path / "Makefile")
    return tmp_path


def _make(sandbox: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [MAKE, "--no-print-directory", f"VENV_DIR={sandbox / 'venv'}", *args],
        cwd=sandbox,
        env={"PATH": str(sandbox / "bin")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_bootstrap_leaves_an_installed_hatch_alone(sandbox: Path) -> None:
    log = _pip_log(sandbox)
    _stub(sandbox / "venv/bin/hatch")
    result = _make(sandbox, "bootstrap")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not log.exists()


def test_bootstrap_installs_only_hatch_when_it_is_missing(sandbox: Path) -> None:
    log = _pip_log(sandbox)
    result = _make(sandbox, "bootstrap")
    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text() == "install hatch\n"


def test_routine_targets_do_not_upgrade_pip(sandbox: Path) -> None:
    result = _make(sandbox, "-n", "test")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "hatch run test" in result.stdout
    assert "--upgrade pip" not in result.stdout


def test_check_type_checks_once(sandbox: Path) -> None:
    """``hatch run lint`` already ends with the type check, so ``check`` must not add another."""
    result = _make(sandbox, "-n", "check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("hatch run lint") == 1
    assert "hatch run typecheck" not in result.stdout
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["tool"]["hatch"]["envs"]["default"]["scripts"]
    assert "hatch run typecheck" in scripts["lint"]


@pytest.mark.parametrize("missing", [set(), set(OPTIONAL)])
def test_doctor_passes_when_every_required_tool_exists(sandbox: Path, missing: set[str]) -> None:
    _install_tools(sandbox, missing)
    result = _make(sandbox, "doctor")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MISSING" not in result.stdout
    for tool in missing:
        assert f"missing  {tool} (optional" in result.stdout


@pytest.mark.parametrize("tool", REQUIRED)
def test_doctor_fails_when_a_required_tool_is_missing(sandbox: Path, tool: str) -> None:
    _install_tools(sandbox, {tool})
    result = _make(sandbox, "doctor")
    name = str(sandbox / "venv/bin/hatch") if tool == "hatch" else tool
    assert result.returncode != 0
    assert f"MISSING  {name} (required)" in result.stdout
    assert result.stdout.count("MISSING  ") == 1


def test_doctor_treats_a_non_executable_hatch_as_missing(sandbox: Path) -> None:
    """Bootstrap tests ``-x``; ``command -v`` alone accepts any existing path."""
    _install_tools(sandbox, set())
    (sandbox / "venv/bin/hatch").chmod(0o644)
    result = _make(sandbox, "doctor")
    assert result.returncode != 0
    assert "MISSING  " in result.stdout


def test_doctor_neither_installs_nor_writes(sandbox: Path) -> None:
    log = _pip_log(sandbox)  # a stub pip and no Hatch: bootstrap would install here
    before = sorted(sandbox.rglob("*"))
    result = _make(sandbox, "doctor")
    assert result.returncode != 0
    assert not log.exists()
    assert sorted(sandbox.rglob("*")) == before
