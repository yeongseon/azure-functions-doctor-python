"""Walkthrough guard for ``check_binding_connection_resolution`` (issue #663).

Gap audited: ``tests/test_binding_connection_resolution.py`` covers the handler and
``tests/test_examples.py`` covers the broken fixture, but nothing showed the same checked-in
fixture becoming valid with safe placeholder settings, or tied the troubleshooting walkthrough
to that behavior.
"""

import json
from pathlib import Path
import shutil

from azure_functions_doctor.doctor import CheckResult, Doctor

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "examples" / "v2" / "broken-unresolved-connection"
SAMPLE = FIXTURE / "local.settings.sample.json"
RULE_ID = "check_binding_connection_resolution"
TROUBLESHOOTING = ROOT / "docs" / "troubleshooting.md"


def _finding(project: Path) -> CheckResult:
    results = Doctor(str(project), profile="deploy").run_all_checks()
    return next(
        item for section in results for item in section["items"] if item["rule_id"] == RULE_ID
    )


def _fixed_copy(tmp_path: Path, values: dict[str, str]) -> Path:
    project = tmp_path / "fixed"
    shutil.copytree(FIXTURE, project)
    (project / "local.settings.json").write_text(
        json.dumps({"IsEncrypted": False, "Values": values}), encoding="utf-8"
    )
    return project


def test_checked_in_fixture_warns_for_the_unresolved_setting_name() -> None:
    assert not (FIXTURE / "local.settings.json").exists()
    finding = _finding(FIXTURE)
    assert finding["status"] == "warn"
    assert "MyStorage" in finding["value"]


def test_sample_uses_only_safe_placeholders() -> None:
    values = json.loads(SAMPLE.read_text(encoding="utf-8"))["Values"]
    assert "MyStorage" in values
    for name, value in values.items():
        assert value == "UseDevelopmentStorage=true" or name == "FUNCTIONS_WORKER_RUNTIME", name
    text = SAMPLE.read_text(encoding="utf-8").lower()
    assert not any(marker in text for marker in ("accountkey", "sharedaccesskey", "sig="))


def test_copying_the_sample_resolves_the_finding(tmp_path: Path) -> None:
    values = json.loads(SAMPLE.read_text(encoding="utf-8"))["Values"]
    finding = _finding(_fixed_copy(tmp_path, values))
    assert finding["status"] == "pass"
    assert "resolve to configured settings" in finding["value"]


def test_identity_based_group_also_resolves_without_a_secret_value(tmp_path: Path) -> None:
    project = _fixed_copy(tmp_path, {"MyStorage__accountName": "<storage-account-name>"})
    assert _finding(project)["status"] == "pass"


def test_resolution_matches_the_setting_name_not_its_value(tmp_path: Path) -> None:
    # A correct-looking value under the wrong name does not help: the match is by name.
    project = _fixed_copy(tmp_path, {"MyStorageTypo": "UseDevelopmentStorage=true"})
    assert _finding(project)["status"] == "warn"
    # And an empty-looking placeholder under the right name resolves it.
    assert (
        _finding(_fixed_copy(tmp_path / "again", {"MyStorage": "<placeholder>"}))["status"]
        == "pass"
    )


def test_troubleshooting_walkthrough_matches_the_fixture() -> None:
    text = TROUBLESHOOTING.read_text(encoding="utf-8")
    section = text.split("### Binding connection warning names an unconfigured setting")[1]
    section = section.split("\n### ")[0]
    assert "examples/v2/broken-unresolved-connection" in section
    assert "local.settings.sample.json" in section
    assert "name" in section and "value" in section and "never reads, prints" in section
    assert RULE_ID in section
