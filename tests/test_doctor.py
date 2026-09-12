import json
import os
from pathlib import Path
import tempfile

import pytest

from azure_functions_doctor.doctor import Doctor


def test_doctor_checks_pass() -> None:
    """Tests that the Doctor class runs checks and returns results."""
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "function_app.py"), "w") as f:
            f.write("import azure.functions as func\napp = func.FunctionApp()\n")
        with open(os.path.join(tmp, "host.json"), "w") as f:
            json.dump({"version": "2.0"}, f)
        with open(os.path.join(tmp, "requirements.txt"), "w") as f:
            f.write("azure-functions==1.13.0")

        doctor = Doctor(tmp)
        results = doctor.run_all_checks()

        assert isinstance(results, list)
        assert all("title" in section and "items" in section for section in results)

        item_map = {
            str(item.get("label", "")): str(item.get("status", ""))
            for section in results
            for item in section["items"]
        }

        assert "Python version" in item_map
        assert item_map.get("host.json") == "pass"
        assert item_map.get("requirements.txt") == "pass"
    # local.settings.json is optional; warn when missing
    assert item_map.get("local.settings.json") == "warn"


def test_missing_files() -> None:
    """Tests that empty projects fail fast as unknown programming models."""
    with tempfile.TemporaryDirectory() as tmp:
        doctor = Doctor(tmp)
        results = doctor.run_all_checks()

    item_map = {
        str(item.get("label", "")): str(item.get("status", ""))
        for section in results
        for item in section["items"]
    }

    assert item_map == {"Python v2 programming model was not detected": "fail"}


def test_custom_rules_path() -> None:
    """Tests that a custom rules file path is honored."""
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "function_app.py"), "w") as f:
            f.write("import azure.functions as func\napp = func.FunctionApp()\n")
        rules = [
            {
                "id": "check_custom_env",
                "category": "environment",
                "section": "custom",
                "label": "Custom env",
                "description": "Checks if CUSTOM_ENV is set.",
                "type": "env_var_exists",
                "required": True,
                "severity": "error",
                "condition": {"target": "CUSTOM_ENV"},
                "hint": "Set CUSTOM_ENV for this check.",
                "check_order": 1,
            }
        ]
        rules_path = Path(tmp) / "rules.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")

        results = Doctor(tmp, rules_path=rules_path).run_all_checks()

        assert len(results) == 1
        assert results[0]["items"][0].get("label") == "Custom env"


def test_custom_rules_path_invalid_raises() -> None:
    """Tests that Doctor raises ValueError when rules_path is not an existing file."""
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="rules_path must be an existing file"):
            Doctor(tmp, rules_path=Path(tmp) / "nonexistent.json")
        with pytest.raises(ValueError, match="rules_path must be an existing file"):
            Doctor(tmp, rules_path=Path(tmp))  # directory, not file


def test_profile_minimal_filters_optional_rules() -> None:
    """Tests that the minimal profile excludes optional rules."""
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "function_app.py"), "w") as f:
            f.write("import azure.functions as func\napp = func.FunctionApp()\n")
        with open(os.path.join(tmp, "host.json"), "w") as f:
            json.dump({"version": "2.0"}, f)
        with open(os.path.join(tmp, "requirements.txt"), "w") as f:
            f.write("azure-functions==1.13.0")

        doctor = Doctor(tmp, profile="minimal")
        results = doctor.run_all_checks()

        item_labels = {
            str(item.get("label", "")) for section in results for item in section["items"]
        }
        assert "local.settings.json" not in item_labels


def _write_minimal_v2_app(tmp: str) -> None:
    with open(os.path.join(tmp, "function_app.py"), "w") as f:
        f.write("import azure.functions as func\napp = func.FunctionApp()\n")
    with open(os.path.join(tmp, "host.json"), "w") as f:
        json.dump({"version": "2.0"}, f)
    with open(os.path.join(tmp, "requirements.txt"), "w") as f:
        f.write("azure-functions==1.13.0")


def test_profile_development_runs_dev_env_checks() -> None:
    """The development profile runs local dev-environment checks (#356)."""
    with tempfile.TemporaryDirectory() as tmp:
        _write_minimal_v2_app(tmp)

        doctor = Doctor(tmp, profile="development")
        results = doctor.run_all_checks()

        rule_ids = {
            str(item.get("rule_id", "")) for section in results for item in section["items"]
        }
        assert rule_ids == {
            "check_venv",
            "check_python_executable",
            "check_func_cli",
            "check_func_core_tools_version",
            "check_local_settings",
        }


def test_profile_deploy_excludes_dev_and_integration() -> None:
    """The deploy profile keeps core deploy rules, drops dev-env + integration (#356)."""
    with tempfile.TemporaryDirectory() as tmp:
        _write_minimal_v2_app(tmp)

        doctor = Doctor(tmp, profile="deploy")
        results = doctor.run_all_checks()

        rule_ids = {
            str(item.get("rule_id", "")) for section in results for item in section["items"]
        }
        # Developer-environment checks are excluded.
        assert "check_venv" not in rule_ids
        assert "check_local_settings" not in rule_ids
        # Integration-group rules are excluded.
        assert "check_langgraph_anonymous_auth" not in rule_ids
        assert "check_otel_trace_context_activation" not in rule_ids
        # Core deploy-correctness rules are present.
        assert "check_python_version" in rule_ids
        assert "check_host_json" in rule_ids


def test_get_report_properties_includes_target_python(tmp_path: Path) -> None:
    """Tests report properties expose programming model and target Python."""
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n",
        encoding="utf-8",
    )
    doctor = Doctor(str(tmp_path), target_python="3.12")

    assert doctor.get_report_properties() == {
        "programming_model": "v2",
        "target_python": "3.12",
        "deployment_mode": "remote-build",
        "hosting_plan": None,
    }


def test_invalid_profile_raises() -> None:
    """Tests that an invalid profile raises a ValueError."""
    with tempfile.TemporaryDirectory() as tmp:
        doctor = Doctor(tmp, profile="unknown")
        with pytest.raises(ValueError, match="Profile must be one of"):
            doctor.run_all_checks()


def test_v2_compatibility_check() -> None:
    """Test that v2 projects (with decorators) work normally."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create a v2 project with decorators
        with open(os.path.join(tmp, "func.py"), "w") as f:
            f.write(
                "from azure.functions import App\n"
                "@app.route('/hello')\n"
                "def main(req):\n"
                "    return 'ok'\n"
            )

        # Should not raise any exception
        doctor = Doctor(tmp)
        results = doctor.run_all_checks()

        # Should have normal results (no function mode check)
        assert len(results) > 0


def test_v1_signal_ignores_excluded_directories(tmp_path: Path) -> None:
    excluded = tmp_path / "dist" / "legacy"
    excluded.mkdir(parents=True)
    (excluded / "function.json").write_text("{}", encoding="utf-8")

    doctor = Doctor(str(tmp_path))

    assert doctor._has_v1_signals() is False


def test_load_rules_invalid_schema_raises_value_error(tmp_path: Path) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n",
        encoding="utf-8",
    )
    bad_rules = tmp_path / "bad_rules.json"
    bad_rules.write_text(json.dumps([{"id": "r1"}]), encoding="utf-8")

    doctor = Doctor(str(tmp_path), rules_path=bad_rules)

    with pytest.raises(ValueError, match="Invalid rules file"):
        doctor.load_rules()


def test_resolve_severity_gate_tier_fallback_from_required() -> None:
    """Explicit severity/gate/tier win; otherwise they fall back to ``required``."""
    from typing import cast

    from azure_functions_doctor.doctor import (
        _resolve_gate,
        _resolve_severity,
        _resolve_tier,
    )
    from azure_functions_doctor.handlers import Rule

    def rule(**kwargs: object) -> Rule:
        return cast(Rule, kwargs)

    # Explicit values are honored.
    explicit = rule(
        severity="info",
        gate=False,
        tier="experimental",
        required=True,
    )
    assert _resolve_severity(explicit) == "info"
    assert _resolve_gate(explicit) is False
    assert _resolve_tier(explicit) == "experimental"

    # Fallbacks derive from ``required=True``.
    required_true = rule(required=True)
    assert _resolve_severity(required_true) == "error"
    assert _resolve_gate(required_true) is True
    assert _resolve_tier(required_true) == "core"

    # Fallbacks derive from ``required=False``.
    required_false = rule(required=False)
    assert _resolve_severity(required_false) == "warning"
    assert _resolve_gate(required_false) is False
    assert _resolve_tier(required_false) == "extended"

    # Invalid explicit values are ignored in favor of the fallback.
    invalid = rule(severity="bogus", tier="bogus", required=False)
    assert _resolve_severity(invalid) == "warning"
    assert _resolve_tier(invalid) == "extended"
