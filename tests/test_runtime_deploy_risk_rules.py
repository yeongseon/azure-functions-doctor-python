"""Tests for the Azure runtime and deploy-risk diagnostic rules (issue #289).

Covers five new rule handlers -- ``functions_extension_version``,
``linux_fx_version``, ``host_json_log_level_conflict``,
``dev_storage_connection`` and ``unpinned_requirements`` -- plus the two
deploy-risk structural changes: the Python-version x hosting-plan matrix in
``target_resolver`` and the ``container`` / ``local-prebuilt`` deployment modes
(CLI validation and ``is_local_prebuilt_deployment``).
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest
import typer

from azure_functions_doctor.cli import _validate_inputs
from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    is_local_prebuilt_deployment,
)
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.target_resolver import is_supported_python_for_plan

registry = HandlerRegistry()


def _result(rule_type: str, path: Path, condition: dict[str, Any] | None = None) -> HandlerResult:
    rule = cast(Rule, {"type": rule_type, "required": False, "condition": condition or {}})
    return registry.handle(rule, path)


def _write(path: Path, name: str, content: str) -> None:
    (path / name).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# functions_extension_version
# ---------------------------------------------------------------------------


def test_functions_extension_version_skips_without_settings(tmp_path: Path) -> None:
    assert _result("functions_extension_version", tmp_path)["status"] == "skip"


def test_functions_extension_version_fails_when_missing_key(tmp_path: Path) -> None:
    _write(tmp_path, "local.settings.json", json.dumps({"Values": {"OTHER": "x"}}))
    result = _result("functions_extension_version", tmp_path)
    assert result["status"] == "fail"
    assert "not set" in result["detail"]


def test_functions_extension_version_fails_on_legacy(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"FUNCTIONS_EXTENSION_VERSION": "~3"}}),
    )
    result = _result("functions_extension_version", tmp_path)
    assert result["status"] == "fail"
    assert "~3" in result["detail"]


def test_functions_extension_version_passes_on_v4(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"FUNCTIONS_EXTENSION_VERSION": "~4"}}),
    )
    assert _result("functions_extension_version", tmp_path)["status"] == "pass"


def test_functions_extension_version_respects_condition_value(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"FUNCTIONS_EXTENSION_VERSION": "~4"}}),
    )
    result = _result("functions_extension_version", tmp_path, {"value": "~5"})
    assert result["status"] == "fail"


def test_functions_extension_version_handles_invalid_json(tmp_path: Path) -> None:
    _write(tmp_path, "local.settings.json", "{not json")
    assert _result("functions_extension_version", tmp_path)["status"] == "fail"


# ---------------------------------------------------------------------------
# linux_fx_version
# ---------------------------------------------------------------------------


def test_linux_fx_version_skips_without_bicep(tmp_path: Path) -> None:
    assert _result("linux_fx_version", tmp_path)["status"] == "skip"


def test_linux_fx_version_passes_on_supported(tmp_path: Path) -> None:
    _write(tmp_path, "main.bicep", "linuxFxVersion: 'Python|3.12'")
    assert _result("linux_fx_version", tmp_path)["status"] == "pass"


def test_linux_fx_version_fails_on_unsupported(tmp_path: Path) -> None:
    _write(tmp_path, "main.bicep", 'linuxFxVersion: "Python|3.9"')
    result = _result("linux_fx_version", tmp_path)
    assert result["status"] == "fail"
    assert "Python|3.9" in result["detail"]


def test_linux_fx_version_scans_nested_infra(tmp_path: Path) -> None:
    infra = tmp_path / "infra"
    infra.mkdir()
    _write(infra, "main.bicep", "linuxFxVersion='Python|3.15'")
    assert _result("linux_fx_version", tmp_path)["status"] == "fail"


# ---------------------------------------------------------------------------
# host_json_log_level_conflict
# ---------------------------------------------------------------------------


def test_log_level_conflict_skips_without_host_json(tmp_path: Path) -> None:
    assert _result("host_json_log_level_conflict", tmp_path)["status"] == "skip"


def test_log_level_conflict_skips_without_default(tmp_path: Path) -> None:
    _write(tmp_path, "host.json", json.dumps({"logging": {"logLevel": {"Function": "Warning"}}}))
    assert _result("host_json_log_level_conflict", tmp_path)["status"] == "skip"


def test_log_level_conflict_passes_when_consistent(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "host.json",
        json.dumps({"logging": {"logLevel": {"default": "Warning", "Function": "Error"}}}),
    )
    assert _result("host_json_log_level_conflict", tmp_path)["status"] == "pass"


def test_log_level_conflict_fails_when_category_more_verbose(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "host.json",
        json.dumps({"logging": {"logLevel": {"default": "Warning", "Function": "Information"}}}),
    )
    result = _result("host_json_log_level_conflict", tmp_path)
    assert result["status"] == "fail"
    assert "Function" in result["detail"]


def test_log_level_conflict_fails_on_unknown_default(tmp_path: Path) -> None:
    _write(tmp_path, "host.json", json.dumps({"logging": {"logLevel": {"default": "Bogus"}}}))
    assert _result("host_json_log_level_conflict", tmp_path)["status"] == "fail"


# ---------------------------------------------------------------------------
# dev_storage_connection
# ---------------------------------------------------------------------------


def test_dev_storage_passes_when_absent(tmp_path: Path) -> None:
    _write(tmp_path, "main.bicep", "param location string")
    assert _result("dev_storage_connection", tmp_path)["status"] == "pass"


def test_dev_storage_ignores_local_settings(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"AzureWebJobsStorage": "UseDevelopmentStorage=true"}}),
    )
    assert _result("dev_storage_connection", tmp_path)["status"] == "pass"


def test_dev_storage_fails_in_bicep(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.bicep",
        "name: 'AzureWebJobsStorage'\nvalue: 'UseDevelopmentStorage=true'",
    )
    result = _result("dev_storage_connection", tmp_path)
    assert result["status"] == "fail"
    assert "main.bicep" in result["detail"]


# ---------------------------------------------------------------------------
# unpinned_requirements
# ---------------------------------------------------------------------------


def test_unpinned_requirements_skips_without_file(tmp_path: Path) -> None:
    assert _result("unpinned_requirements", tmp_path)["status"] == "skip"


def test_unpinned_requirements_passes_when_pinned(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions==1.21.3\nrequests>=2.0,<3.0\n")
    assert _result("unpinned_requirements", tmp_path)["status"] == "pass"


def test_unpinned_requirements_fails_without_specifier(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "requests\n")
    result = _result("unpinned_requirements", tmp_path)
    assert result["status"] == "fail"
    assert "no version specifier" in result["detail"]


def test_unpinned_requirements_fails_without_upper_bound(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "requests>=2.0\n")
    result = _result("unpinned_requirements", tmp_path)
    assert result["status"] == "fail"
    assert "no upper bound" in result["detail"]


def test_unpinned_requirements_ignores_comments_and_flags(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "requirements.txt",
        "# a comment\n-r other.txt\nazure-functions==1.21.3\n",
    )
    assert _result("unpinned_requirements", tmp_path)["status"] == "pass"


# ---------------------------------------------------------------------------
# Python x hosting-plan matrix (target_resolver)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "plan", "expected"),
    [
        ("3.12", "linux-consumption", True),
        ("3.14", "linux-consumption", False),
        ("3.14", "flex-consumption", True),
        ("3.14", "premium", True),
        ("3.9", "dedicated", False),
        ("3.14", "unknown-plan", True),  # falls back to plan-agnostic support
        ("3.9", "unknown-plan", False),
        ("not-a-version", "linux-consumption", False),
    ],
)
def test_is_supported_python_for_plan(version: str, plan: str, expected: bool) -> None:
    assert is_supported_python_for_plan(version, plan) is expected


# ---------------------------------------------------------------------------
# CLI hosting-plan validation
# ---------------------------------------------------------------------------


def test_validate_inputs_rejects_unknown_hosting_plan(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        _validate_inputs(str(tmp_path), "table", None, hosting_plan="serverless")


def test_validate_inputs_rejects_invalid_python_plan_combo(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        _validate_inputs(
            str(tmp_path), "table", None, target_python="3.14", hosting_plan="linux-consumption"
        )


def test_validate_inputs_accepts_valid_python_plan_combo(tmp_path: Path) -> None:
    _validate_inputs(
        str(tmp_path), "table", None, target_python="3.12", hosting_plan="linux-consumption"
    )


# ---------------------------------------------------------------------------
# Container / local-prebuilt deployment modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["local", "local-prebuilt", "container"])
def test_is_local_prebuilt_deployment_recognizes_modes(tmp_path: Path, mode: str) -> None:
    context = cast(Any, {"deployment_mode": mode})
    assert is_local_prebuilt_deployment(tmp_path, context) is True


def test_is_local_prebuilt_deployment_false_for_remote_build(tmp_path: Path) -> None:
    context = cast(Any, {"deployment_mode": "remote-build"})
    assert is_local_prebuilt_deployment(tmp_path, context) is False
