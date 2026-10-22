"""Executable contracts for developer commands, separate from the product CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("url", ["", "not-a-url", "https://", "http://localhost:7071"])
def test_azure_preflight_fails_before_tests_when_url_is_not_deployed(
    tmp_path: Path, url: str
) -> None:
    # Given an absent or invalid deployed URL and no possible test tree.
    environment = dict(os.environ, PYTHONPATH=str(ROOT), E2E_BASE_URL=url)
    # When invoking the actual verification CLI.
    result = subprocess.run(
        [sys.executable, "-m", "tools.verification", "azure-e2e"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    # Then no test process runs and the saved result is explicitly incomplete.
    assert result.returncode != 0
    path = tmp_path / "test-results/azure-e2e/summary.json"
    assert path.exists(), result.stderr
    summary = json.loads(path.read_text())
    assert (summary["status"], summary["selected"]) == ("INCOMPLETE", 0)
    assert not (path.parent / "logs/runner.log").exists()


@pytest.mark.parametrize(
    "target", ["doctor", "check", "test", "integration", "verify", "report", "clean"]
)
def test_routine_targets_never_install_hatch_or_upgrade_pip(target: str) -> None:
    # Given a routine target, when expanding its recipe without executing it.
    result = subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True, text=True)
    # Then setup is explicit rather than an implicit global change.
    assert result.returncode == 0, result.stderr
    assert "install --upgrade pip" not in result.stdout
    assert "install hatch" not in result.stdout


def test_ci_preserves_explicit_interpreter_and_check_all_is_exact_alias() -> None:
    # Given an explicitly selected matrix interpreter.
    result = subprocess.run(
        ["make", "--no-print-directory", "-n", "test", "CI=true", "PYTHON=matrix-python"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # Then no Hatch substitution occurs and the compatibility alias adds no work.
    assert result.stdout.strip() == "matrix-python -m tools.verification test"
    assert "check-all: verify\n" in (ROOT / "Makefile").read_text()


def test_check_runs_types_once_without_heavy_system_prerequisites() -> None:
    # Given the complete non-mutating quality target.
    result = subprocess.run(["make", "-n", "check"], cwd=ROOT, capture_output=True, text=True)
    # Then it runs strict types once and keeps the lightweight Mermaid linter.
    assert result.returncode == 0
    assert result.stdout.count("-m mypy") == 1
    assert "scripts/lint_mermaid.py" in result.stdout
    assert "mmdc" not in result.stdout
    assert "docker" not in result.stdout
