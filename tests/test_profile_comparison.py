"""Offline profile comparison on one checked-in project (issue #662).

Documents and pins which rules each profile selects for
``examples/v2/broken-flex-runtime-config``. Environment-sensitive rules (local tooling,
git state, app settings) are intentionally not asserted.
"""

from pathlib import Path
import re

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli
from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.profiles import PROFILE_NAMES

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "examples" / "v2" / "broken-flex-runtime-config"
PAGE = ROOT / "docs" / "profile_comparison.md"
FLEX_RULE = "check_flex_runtime_config"

MINIMAL_RULES = {
    "check_python_version",
    "check_requirements_txt",
    "check_azure_functions_library",
    "check_host_json",
    "check_host_json_version",
    "check_durable_nondeterminism",
}
DEVELOPMENT_RULES = {
    "check_venv",
    "check_python_executable",
    "check_local_settings",
    "check_func_cli",
    "check_func_core_tools_version",
}

runner = CliRunner()


def _statuses(profile: str) -> dict[str, str]:
    results = Doctor(str(PROJECT), profile=profile).run_all_checks()
    return {item["rule_id"]: item["status"] for section in results for item in section["items"]}


def test_minimal_and_development_profiles_select_exact_stable_subsets() -> None:
    assert set(_statuses("minimal")) == MINIMAL_RULES
    assert set(_statuses("development")) == DEVELOPMENT_RULES


def test_flex_runtime_rule_is_selected_only_by_deploy_and_full() -> None:
    assert _statuses("deploy")[FLEX_RULE] == "fail"
    assert _statuses("full")[FLEX_RULE] == "fail"
    assert FLEX_RULE not in _statuses("minimal")
    assert FLEX_RULE not in _statuses("development")


def test_profile_selection_is_nested_for_minimal_deploy_full() -> None:
    minimal, deploy, full = (set(_statuses(p)) for p in ("minimal", "deploy", "full"))
    assert minimal <= deploy <= full
    assert DEVELOPMENT_RULES <= full
    assert not DEVELOPMENT_RULES & deploy


@pytest.mark.parametrize(
    ("profile", "exit_code"),
    [("minimal", 0), ("deploy", 1), ("development", 0), ("full", 1)],
)
def test_exit_code_differs_by_profile_on_same_project(profile: str, exit_code: int) -> None:
    result = runner.invoke(cli, ["doctor", "--path", str(PROJECT), "--profile", profile])
    assert result.exit_code == exit_code


def test_minimal_clean_run_does_not_mean_the_flex_runtime_is_healthy() -> None:
    # Not selected is not the same as passed: the rule is absent from the results, not green,
    # and the unsupported declared runtime is still reported by the profiles that select it.
    assert FLEX_RULE not in _statuses("minimal")
    assert _statuses("deploy")[FLEX_RULE] == "fail"


def test_page_documents_every_profile_and_its_stable_subset() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for profile in PROFILE_NAMES:
        assert f"--profile {profile}" in text
    subset = text.split("Stable subset used by")[1].split("## Environment-sensitive")[0]
    minimal_part, development_part = subset.split("- `development` selects exactly")
    documented_minimal = set(re.findall(r"`(check_\w+)`", minimal_part.split("- `deploy`")[0]))
    documented_development = set(re.findall(r"`(check_\w+)`", development_part))
    assert documented_minimal == MINIMAL_RULES
    assert documented_development == DEVELOPMENT_RULES
    assert "not** evidence that the project is healthy" in text
