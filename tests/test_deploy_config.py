"""Tests for deploy-config ingestion (issue #347).

Exercises :func:`resolve_target_config` across the four canonical hosting plans
(Flex Consumption, Linux Consumption, Premium, Dedicated), extension-version /
deployment-storage / app-settings extraction, the documented resolution
precedence (override > IaC > local signal > unknown) including a
conflicting-sources case, and graceful degradation when no infrastructure is
present. Also verifies the Doctor/CLI wiring that surfaces ``hosting_plan`` in
report properties.
"""

import json
from pathlib import Path

from azure_functions_doctor.deploy_config import (
    PLAN_DEDICATED,
    PLAN_FLEX_CONSUMPTION,
    PLAN_LINUX_CONSUMPTION,
    PLAN_PREMIUM,
    SOURCE_OVERRIDE,
    SOURCE_UNKNOWN,
    ResolvedField,
    TargetConfig,
    resolve_target_config,
)
from azure_functions_doctor.doctor import Doctor


def _write(path: Path, name: str, content: str) -> None:
    (path / name).write_text(content, encoding="utf-8")


def _arm_with_sku(name: str, tier: str) -> str:
    return json.dumps(
        {
            "resources": [
                {
                    "type": "Microsoft.Web/serverfarms",
                    "sku": {"name": name, "tier": tier},
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
# ResolvedField / TargetConfig primitives
# ---------------------------------------------------------------------------


def test_resolved_field_is_known() -> None:
    assert ResolvedField("3.12", "infra/main.bicep").is_known is True
    assert ResolvedField(None, SOURCE_UNKNOWN).is_known is False


def test_target_config_unknown_factory() -> None:
    cfg = TargetConfig.unknown()
    assert cfg.hosting_plan.value is None
    assert cfg.hosting_plan.source == SOURCE_UNKNOWN
    assert cfg.runtime_name.is_known is False
    assert cfg.runtime_version.is_known is False
    assert cfg.extension_version.is_known is False
    assert cfg.deployment_storage.is_known is False
    assert cfg.app_settings == {}


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_absent_infra_degrades_to_unknown(tmp_path: Path) -> None:
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.source == SOURCE_UNKNOWN
    assert cfg.hosting_plan.is_known is False
    assert cfg.runtime_version.is_known is False
    assert cfg.app_settings == {}


def test_unreadable_and_malformed_infra_is_tolerated(tmp_path: Path) -> None:
    _write(tmp_path, "broken.json", "{not valid json")
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.is_known is False


def test_excluded_dirs_are_skipped(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir()
    _write(venv, "main.bicep", "linuxFxVersion: 'Python|3.12'")
    cfg = resolve_target_config(tmp_path)
    assert cfg.runtime_version.is_known is False


# ---------------------------------------------------------------------------
# Hosting-plan detection across the four canonical plans
# ---------------------------------------------------------------------------


def test_flex_consumption_from_function_app_config_bicep(tmp_path: Path) -> None:
    _write(tmp_path, "main.bicep", "resource fa 'x' = {\n  functionAppConfig: {}\n}")
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_FLEX_CONSUMPTION
    assert cfg.hosting_plan.source == "main.bicep"


def test_flex_consumption_from_function_app_config_json(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps({"resources": [{"functionAppConfig": {"runtime": {}}}]}),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_FLEX_CONSUMPTION


def test_linux_consumption_from_dynamic_sku(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("Y1", "Dynamic"))
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_LINUX_CONSUMPTION


def test_premium_from_ep_sku(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("EP1", "ElasticPremium"))
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_PREMIUM


def test_dedicated_from_standard_sku(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("S1", "Standard"))
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_DEDICATED


def test_unrecognized_sku_stays_unknown(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("mystery", "custom"))
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.is_known is False


def test_flex_wins_over_legacy_sku_specificity(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps(
            {
                "resources": [
                    {"functionAppConfig": {}},
                    {"sku": {"name": "S1", "tier": "Standard"}},
                ]
            }
        ),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_FLEX_CONSUMPTION


# ---------------------------------------------------------------------------
# Runtime / extension / storage / app-settings extraction
# ---------------------------------------------------------------------------


def test_runtime_from_linux_fx_version_bicep(tmp_path: Path) -> None:
    _write(tmp_path, "main.bicep", "linuxFxVersion: 'Python|3.12'")
    cfg = resolve_target_config(tmp_path)
    assert cfg.runtime_name.value == "python"
    assert cfg.runtime_version.value == "3.12"


def test_runtime_from_function_app_config_json(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps({"functionAppConfig": {"runtime": {"name": "Python", "version": "3.11"}}}),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.runtime_name.value == "python"
    assert cfg.runtime_version.value == "3.11"


def test_extension_and_storage_and_app_settings_from_json(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps(
            {
                "resources": [
                    {
                        "appSettings": [
                            {"name": "FUNCTIONS_EXTENSION_VERSION", "value": "~4"},
                            {"name": "AzureWebJobsStorage", "value": "conn-str"},
                            {"name": "CUSTOM", "value": "x"},
                        ]
                    }
                ]
            }
        ),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.extension_version.value == "~4"
    assert cfg.deployment_storage.value == "conn-str"
    assert cfg.app_settings["CUSTOM"] == "x"


def test_flex_deployment_storage_value_preferred(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps(
            {"functionAppConfig": {"deployment": {"storage": {"value": "https://flexstore"}}}}
        ),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.deployment_storage.value == "https://flexstore"


def test_extension_and_storage_from_bicep(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.bicep",
        "appSettings: [\n"
        "  {\n    name: 'FUNCTIONS_EXTENSION_VERSION'\n    value: '~4'\n  }\n"
        "  {\n    name: 'AzureWebJobsStorage'\n    value: 'UseDevelopmentStorage=true'\n  }\n"
        "]",
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.extension_version.value == "~4"
    assert cfg.deployment_storage.value == "UseDevelopmentStorage=true"


def test_bicep_emulator_storage_without_explicit_setting(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.bicep",
        "var conn = 'AzureWebJobsStorage'\nvalue: 'UseDevelopmentStorage=true'",
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.deployment_storage.value == "UseDevelopmentStorage=true"


def test_app_settings_ignore_non_string_entries(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps(
            {
                "appSettings": [
                    {"name": "OK", "value": "yes"},
                    {"name": "NUM", "value": 5},
                    "not-a-dict",
                ]
            }
        ),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.app_settings == {"OK": "yes"}


# ---------------------------------------------------------------------------
# Local signals (lowest precedence above unknown)
# ---------------------------------------------------------------------------


def test_local_settings_provide_signals(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps(
            {
                "Values": {
                    "FUNCTIONS_EXTENSION_VERSION": "~4",
                    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
                }
            }
        ),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.extension_version.value == "~4"
    assert cfg.extension_version.source == "local:local.settings.json"
    assert cfg.deployment_storage.value == "UseDevelopmentStorage=true"


def test_local_settings_not_treated_as_infra(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"functionAppConfig": "x"}}),
    )
    cfg = resolve_target_config(tmp_path)
    # local.settings.json is never scanned as deployable infra.
    assert cfg.hosting_plan.is_known is False


def test_local_settings_malformed_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "local.settings.json", "{bad json")
    cfg = resolve_target_config(tmp_path)
    assert cfg.extension_version.is_known is False


def test_local_settings_without_values_block(tmp_path: Path) -> None:
    _write(tmp_path, "local.settings.json", json.dumps({"IsEncrypted": False}))
    cfg = resolve_target_config(tmp_path)
    assert cfg.extension_version.is_known is False


# ---------------------------------------------------------------------------
# Precedence: override > IaC > local > unknown (conflicting-sources case)
# ---------------------------------------------------------------------------


def test_conflicting_sources_precedence(tmp_path: Path) -> None:
    # IaC declares Dedicated + Python 3.11; local declares extension version;
    # CLI overrides both hosting_plan and runtime_version.
    _write(
        tmp_path,
        "main.json",
        json.dumps(
            {
                "resources": [
                    {"sku": {"name": "S1", "tier": "Standard"}},
                    {"functionAppConfig": {"runtime": {"name": "python", "version": "3.11"}}},
                ]
            }
        ),
    )
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"FUNCTIONS_EXTENSION_VERSION": "~4"}}),
    )
    cfg = resolve_target_config(
        tmp_path,
        {"hosting_plan": "premium", "runtime_version": "3.12"},
    )
    # Override wins for both overridable fields.
    assert cfg.hosting_plan.value == "premium"
    assert cfg.hosting_plan.source == SOURCE_OVERRIDE
    assert cfg.runtime_version.value == "3.12"
    assert cfg.runtime_version.source == SOURCE_OVERRIDE
    # IaC wins for non-overridable runtime_name.
    assert cfg.runtime_name.value == "python"
    assert cfg.runtime_name.source == "main.json"
    # Local wins where IaC is silent.
    assert cfg.extension_version.value == "~4"
    assert cfg.extension_version.source == "local:local.settings.json"


def test_iac_beats_local_for_shared_field(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps({"appSettings": [{"name": "FUNCTIONS_EXTENSION_VERSION", "value": "~4"}]}),
    )
    _write(
        tmp_path,
        "local.settings.json",
        json.dumps({"Values": {"FUNCTIONS_EXTENSION_VERSION": "~3"}}),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.extension_version.value == "~4"
    assert cfg.extension_version.source == "main.json"


def test_override_none_values_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("EP1", "ElasticPremium"))
    cfg = resolve_target_config(tmp_path, {"hosting_plan": None, "runtime_version": None})
    assert cfg.hosting_plan.value == PLAN_PREMIUM


# ---------------------------------------------------------------------------
# Doctor / CLI wiring
# ---------------------------------------------------------------------------


def test_doctor_surfaces_hosting_plan_in_report_properties(tmp_path: Path) -> None:
    doctor = Doctor(str(tmp_path), hosting_plan="premium")
    props = doctor.get_report_properties()
    assert props["hosting_plan"] == "premium"


def test_doctor_hosting_plan_defaults_to_none(tmp_path: Path) -> None:
    doctor = Doctor(str(tmp_path))
    assert doctor.get_report_properties()["hosting_plan"] is None


def test_flex_from_fc1_sku(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("FC1", "FlexConsumption"))
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_FLEX_CONSUMPTION


def test_dedicated_from_sku_name(tmp_path: Path) -> None:
    _write(tmp_path, "plan.json", _arm_with_sku("P1v2", "unknown-tier"))
    cfg = resolve_target_config(tmp_path)
    assert cfg.hosting_plan.value == PLAN_DEDICATED


def test_flex_deployment_storage_non_string_value_ignored(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps(
            {
                "functionAppConfig": {
                    "deployment": {"storage": {"value": 123, "type": "blobContainer"}}
                }
            }
        ),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.deployment_storage.is_known is False


def test_flex_deployment_storage_non_dict_ignored(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "main.json",
        json.dumps({"functionAppConfig": {"deployment": {"storage": "not-a-dict"}}}),
    )
    cfg = resolve_target_config(tmp_path)
    assert cfg.deployment_storage.is_known is False
