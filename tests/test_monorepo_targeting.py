"""Targeting guard for the two-app monorepo walkthrough (issue #666).

Gap audited: ``tests/test_examples.py`` and ``tests/test_cli.py`` pin the SARIF URI rebasing for
one monorepo app, but nothing proved that ``--path`` on one app never reports the sibling app,
and the single-app example gave no per-app invocation pair or comparison.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli

ROOT = Path(__file__).resolve().parent.parent
MONOREPO = ROOT / "examples" / "monorepo"
README = MONOREPO / "README.md"

runner = CliRunner()


def _run(
    path: str, monkeypatch: pytest.MonkeyPatch, fmt: str = "json"
) -> tuple[int, str, dict[str, Any]]:
    monkeypatch.chdir(MONOREPO)
    result = runner.invoke(cli, ["doctor", "--path", path, "--profile", "deploy", "--format", fmt])
    return result.exit_code, result.output, json.loads(result.output)


def _statuses(report: dict[str, Any]) -> dict[str, str]:
    return {i["rule_id"]: i["status"] for section in report["results"] for i in section["items"]}


def test_api_run_reports_only_the_api_app(monkeypatch: pytest.MonkeyPatch) -> None:
    exit_code, output, report = _run("services/api", monkeypatch)
    statuses = _statuses(report)
    assert exit_code == 1
    assert report["metadata"]["target_path"].endswith("services/api")
    assert statuses["check_host_json"] == "fail"
    assert statuses["check_host_json_version"] == "fail"
    assert "services/worker" not in output
    assert "pyodbc" not in output


def test_worker_run_reports_only_the_worker_app(monkeypatch: pytest.MonkeyPatch) -> None:
    exit_code, output, report = _run("services/worker", monkeypatch)
    statuses = _statuses(report)
    assert exit_code == 0
    assert report["metadata"]["target_path"].endswith("services/worker")
    assert statuses["check_host_json"] == "pass"
    assert statuses["check_native_dependency_risk"] == "warn"
    assert "pyodbc" in output
    assert "services/api" not in output


def test_sarif_uris_stay_inside_the_targeted_app(monkeypatch: pytest.MonkeyPatch) -> None:
    for app, sibling in (("api", "worker"), ("worker", "api")):
        _, _, sarif = _run(f"services/{app}", monkeypatch, fmt="sarif")
        uris = {
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for r in sarif["runs"][0]["results"]
            if r.get("locations")
        }
        assert all(uri.startswith(f"services/{app}/") for uri in uris), uris
        assert not any(f"services/{sibling}" in uri for uri in uris)


def test_root_path_is_not_equivalent_to_scanning_both_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exit_code, output, report = _run(".", monkeypatch)
    statuses = _statuses(report)
    # File-based checks look at the directory itself: neither app's manifests are used.
    assert exit_code == 1
    assert statuses["check_host_json"] == "fail"
    assert statuses["check_requirements_txt"] == "fail"
    assert "pyodbc" not in output


def test_readme_documents_a_command_per_app_and_no_auto_discovery() -> None:
    text = README.read_text(encoding="utf-8")
    for app in ("api", "worker"):
        assert f"azure-functions-doctor doctor --path services/{app} --profile deploy\n" in text
    assert "does **not**\ndiscover apps" in text
