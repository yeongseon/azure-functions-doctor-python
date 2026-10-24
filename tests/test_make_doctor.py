"""``make`` prerequisites: bootstrap installs Hatch only when it is missing.

Each test runs ``make`` on a scratch copy of the Makefile with ``PATH`` limited to a stub
directory and a stub ``pip`` inside the scratch virtual environment, so nothing is installed
and no network is used.
"""

from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import stat
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKE = shutil.which("make") or "make"


def _stub(path: Path, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}exit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _pip_log(sandbox: Path) -> Path:
    """Put a stub ``pip`` in the scratch venv; it appends its arguments to the returned file."""
    log = sandbox / "pip.log"
    _stub(sandbox / "venv/bin/pip", f'echo "$*" >> {shlex.quote(str(log))}\n')
    return log


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
