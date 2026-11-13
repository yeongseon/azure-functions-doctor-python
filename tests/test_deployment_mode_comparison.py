"""Offline deployment-mode comparison on one synthetic project (issue #665).

Gap audited: ``tests/test_pyproject_dependency_manifest.py`` covers pyproject-only manifests
per handler with temporary files, and ``tests/test_runtime_deploy_risk_rules.py`` covers
``is_local_prebuilt_deployment``. Nothing ran the full CLI on a checked-in project under two
deployment modes, so the user-facing difference was undocumented.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import SUPPORTED_DEPLOYMENT_MODES, cli

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "examples" / "v2" / "pyproject-only-dependencies"
CONFIG_DOC = ROOT / "docs" / "configuration.md"
DEPENDENCY_RULES = ("check_requirements_txt", "check_azure_functions_library")

runner = CliRunner()


def _run(mode: str | None) -> tuple[int, dict[str, dict[str, Any]], dict[str, Any]]:
    args = ["doctor", "--path", str(PROJECT), "--profile", "minimal", "--format", "json"]
    if mode is not None:
        args += ["--deployment-mode", mode]
    result = runner.invoke(cli, args)
    report = json.loads(result.output)
    items = {i["rule_id"]: i for section in report["results"] for i in section["items"]}
    return result.exit_code, items, report["metadata"]


def test_project_has_pyproject_only_dependency_manifest() -> None:
    assert (PROJECT / "pyproject.toml").is_file()
    assert not (PROJECT / "requirements.txt").exists()
    assert not (PROJECT / ".python_packages").exists()


@pytest.mark.parametrize("mode", [None, "remote-build"])
def test_remote_build_flags_pyproject_only_dependencies(mode: str | None) -> None:
    exit_code, items, metadata = _run(mode)
    assert metadata["deployment_mode"] == "remote-build"
    assert exit_code == 1
    for rule_id in DEPENDENCY_RULES:
        assert items[rule_id]["status"] == "fail", rule_id
    manifest_detail = items["check_requirements_txt"]["value"]
    assert "Azure remote build installs from requirements.txt" in manifest_detail
    assert "--deployment-mode local" in items["check_azure_functions_library"]["value"]


@pytest.mark.parametrize("mode", ["local", "local-prebuilt", "container"])
def test_prebuilt_modes_accept_pyproject_only_dependencies(mode: str) -> None:
    exit_code, items, metadata = _run(mode)
    assert metadata["deployment_mode"] == mode
    assert exit_code == 0
    for rule_id in DEPENDENCY_RULES:
        assert items[rule_id]["status"] == "pass", rule_id
        assert "local/prebuilt deployment" in items[rule_id]["value"]


def test_only_deployment_mode_changes_between_runs() -> None:
    _, remote, _ = _run("remote-build")
    _, local, _ = _run("local")
    changed = {rule for rule in remote if remote[rule]["status"] != local[rule]["status"]}
    assert changed == set(DEPENDENCY_RULES)


def test_documentation_matches_the_comparison() -> None:
    text = CONFIG_DOC.read_text(encoding="utf-8")
    section = text.split("### Deployment mode comparison")[1].split("\n## ")[0]
    assert "examples/v2/pyproject-only-dependencies" in section
    assert "not Azure certification" in section
    for rule_id in DEPENDENCY_RULES:
        assert f"`{rule_id}`" in section
    # Every non-default mode the CLI accepts is covered by the table.
    for mode in SUPPORTED_DEPLOYMENT_MODES:
        assert mode in section, mode
