"""Smoke tests for the bundled v2 example projects.

Each passing example must satisfy all *required* rule checks.
Each broken example must fail on exactly the one rule it intentionally violates.
"""

from pathlib import Path

import pytest

from azure_functions_doctor.doctor import CheckResult, Doctor

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "v2"

# Required-rule labels (required=True in v2.json) that must pass for every
# healthy example.  Environment-dependent checks (venv, python exe, func CLI)
# are excluded because they depend on the CI machine's setup.
_ALWAYS_PASS_LABELS = {
    "host.json",
    "host.json version",
    "requirements.txt",
    "azure-functions package",
}


def _run_example(example_name: str) -> tuple[Doctor, dict[str, str]]:
    project_path = EXAMPLES_DIR / example_name
    doctor = Doctor(str(project_path))
    results = doctor.run_all_checks()
    item_map = {item["label"]: item["status"] for section in results for item in section["items"]}
    return doctor, item_map


def _items_for_example(example_name: str) -> dict[str, CheckResult]:
    doctor = Doctor(str(EXAMPLES_DIR / example_name))
    return {item["label"]: item for section in doctor.run_all_checks() for item in section["items"]}


# ---------------------------------------------------------------------------
# Passing examples
# ---------------------------------------------------------------------------


class TestPassingExamples:
    """All four healthy examples must pass every structural required check."""

    @pytest.mark.parametrize(
        "example_name",
        ["http-trigger", "timer-trigger", "multi-trigger", "blueprint"],
    )
    def test_required_checks_pass(self, example_name: str) -> None:
        doctor, item_map = _run_example(example_name)
        assert doctor.programming_model == "v2", (
            f"{example_name}: expected programming_model='v2', got {doctor.programming_model!r}"
        )
        for label in _ALWAYS_PASS_LABELS:
            assert item_map.get(label) == "pass", (
                f"{example_name}: expected '{label}' == 'pass', got {item_map.get(label)!r}"
            )

    def test_http_trigger_is_v2_project(self) -> None:
        doctor, item_map = _run_example("http-trigger")
        assert doctor.programming_model == "v2"
        assert item_map.get("host.json") == "pass"
        assert item_map.get("requirements.txt") == "pass"
        assert item_map.get("azure-functions package") == "pass"
        assert item_map.get("Programming model v2") == "pass"

    def test_timer_trigger_is_v2_project(self) -> None:
        doctor, item_map = _run_example("timer-trigger")
        assert doctor.programming_model == "v2"
        assert item_map.get("host.json") == "pass"
        assert item_map.get("requirements.txt") == "pass"
        assert item_map.get("azure-functions package") == "pass"
        assert item_map.get("Programming model v2") == "pass"

    def test_multi_trigger_is_v2_project(self) -> None:
        doctor, item_map = _run_example("multi-trigger")
        assert doctor.programming_model == "v2"
        assert item_map.get("host.json") == "pass"
        assert item_map.get("requirements.txt") == "pass"
        assert item_map.get("azure-functions package") == "pass"
        assert item_map.get("Programming model v2") == "pass"

    def test_blueprint_is_v2_project(self) -> None:
        doctor, item_map = _run_example("blueprint")
        assert doctor.programming_model == "v2"
        assert item_map.get("host.json") == "pass"
        assert item_map.get("requirements.txt") == "pass"
        assert item_map.get("azure-functions package") == "pass"
        assert item_map.get("Programming model v2") == "pass"


# ---------------------------------------------------------------------------
# Broken examples — each must fail on exactly the intended rule
# ---------------------------------------------------------------------------


class TestBrokenExamples:
    """Broken examples must surface exactly the defect they were designed for."""

    def test_broken_missing_host_json_fails_host_json_check(self) -> None:
        _, item_map = _run_example("broken-missing-host-json")
        assert item_map.get("host.json") == "fail", (
            "broken-missing-host-json: expected 'host.json' == 'fail', "
            f"got {item_map.get('host.json')!r}"
        )

    def test_broken_missing_requirements_fails_requirements_check(self) -> None:
        _, item_map = _run_example("broken-missing-requirements")
        assert item_map.get("requirements.txt") == "fail", (
            "broken-missing-requirements: expected 'requirements.txt' == 'fail', "
            f"got {item_map.get('requirements.txt')!r}"
        )

    def test_broken_missing_azure_functions_fails_package_check(self) -> None:
        _, item_map = _run_example("broken-missing-azure-functions")
        assert item_map.get("azure-functions package") == "fail", (
            "broken-missing-azure-functions: expected 'azure-functions package' == 'fail', "
            f"got {item_map.get('azure-functions package')!r}"
        )

    def test_broken_no_v2_decorators_fails_programming_model_detection(self) -> None:
        _, item_map = _run_example("broken-no-v2-decorators")
        assert item_map.get("Python v2 programming model was not detected") == "fail", (
            "broken-no-v2-decorators: expected undetected v2 programming model failure, "
            f"got {item_map!r}"
        )


# ---------------------------------------------------------------------------
# Deploy-profile scenario fixtures (issue #409)
# ---------------------------------------------------------------------------


class TestDeployScenarioExamples:
    """Deploy-rule fixtures: healthy Flex passes; each broken trips exactly its rule."""

    def test_flex_consumption_healthy_passes_deploy_rules(self) -> None:
        _doctor, item_map = _run_example("flex-consumption")
        assert item_map.get("Flex Consumption runtime config") == "pass"
        assert item_map.get("Flex Consumption deprecated app settings") == "pass"
        assert item_map.get("Flex Consumption deployment storage") == "pass"
        assert item_map.get("Dev-storage emulator connection") == "pass"
        for label in _ALWAYS_PASS_LABELS:
            assert item_map.get(label) == "pass", label

    def test_broken_flex_runtime_config_fails_only_that_rule(self) -> None:
        _doctor, item_map = _run_example("broken-flex-runtime-config")
        assert item_map.get("Flex Consumption runtime config") == "fail"
        assert item_map.get("Flex Consumption deprecated app settings") == "pass"
        for label in _ALWAYS_PASS_LABELS:
            assert item_map.get(label) == "pass", label

    def test_broken_flex_deprecated_settings_warns(self) -> None:
        _doctor, item_map = _run_example("broken-flex-deprecated-settings")
        assert item_map.get("Flex Consumption deprecated app settings") == "warn"
        assert item_map.get("Flex Consumption runtime config") == "pass"
        for label in _ALWAYS_PASS_LABELS:
            assert item_map.get(label) == "pass", label

    def test_broken_flex_deployment_storage_warns(self) -> None:
        _doctor, item_map = _run_example("broken-flex-deployment-storage")
        assert item_map.get("Flex Consumption deployment storage") == "warn"
        assert item_map.get("Flex Consumption runtime config") == "pass"
        for label in _ALWAYS_PASS_LABELS:
            assert item_map.get(label) == "pass", label

    def test_broken_dev_storage_leak_warns(self) -> None:
        _doctor, item_map = _run_example("broken-dev-storage-leak")
        assert item_map.get("Dev-storage emulator connection") == "warn"
        for label in _ALWAYS_PASS_LABELS:
            assert item_map.get(label) == "pass", label

    def test_broken_legacy_extension_version_warns_and_lifecycle_fails(self) -> None:
        """The ~3 pin trips the extension-version warn; v3 being out of
        support also fails the runtime lifecycle check (both correct)."""
        _doctor, item_map = _run_example("broken-legacy-extension-version")
        assert item_map.get("Functions extension version") == "warn"
        assert item_map.get("Functions runtime lifecycle") == "fail"
        assert item_map.get("requirements.txt") == "pass"


class TestLocatedFindingExamples:
    def test_validation_integration_locates_both_findings(self) -> None:
        items = _items_for_example("validation-integration")
        assert items["Decorator order"]["status"] == "warn"
        assert items["Decorator order"]["locations"] == [
            {
                "file": "function_app.py",
                "line": 8,
                "message": "Inverted decorator order on function_app.py:inverted",
            }
        ]
        assert items["Endpoint metadata coverage"]["status"] == "warn"
        assert items["Endpoint metadata coverage"]["locations"] == [
            {
                "file": "function_app.py",
                "line": 16,
                "end_line": 17,
                "column": 1,
                "message": (
                    "Route handler missing @validate_http (no endpoint metadata): "
                    "function_app.py:uncovered"
                ),
            }
        ]

    def test_unbound_requirements_locates_unpinned_declaration(self) -> None:
        items = _items_for_example("warn-unbound-requirements")
        assert items["Pinned requirements"]["status"] == "warn"
        assert items["Pinned requirements"]["locations"] == [
            {
                "file": "requirements.txt",
                "line": 2,
                "message": "numpy (>=2.0; no upper bound)",
            }
        ]
        assert items["Native dependency risk"]["status"] == "warn"

    def test_linux_fx_example_reports_infrastructure_source(self) -> None:
        items = _items_for_example("broken-linux-fx-version")
        assert items["Linux runtime (linuxFxVersion)"]["status"] == "warn"
        assert items["Linux runtime (linuxFxVersion)"]["locations"] == [
            {"file": "main.bicep", "message": "linuxFxVersion Python|3.9 is unsupported"}
        ]

    def test_unresolved_connection_locates_trigger(self) -> None:
        items = _items_for_example("broken-unresolved-connection")
        assert items["Binding connection resolution"]["status"] == "warn"
        assert items["Binding connection resolution"]["locations"] == [
            {
                "file": "function_app.py",
                "line": 6,
                "message": (
                    "Binding connection 'MyStorage' (function_app.py:process) has no matching "
                    "app setting"
                ),
            }
        ]

    def test_nondeterministic_orchestrator_locates_random_call(self) -> None:
        items = _items_for_example("warn-nondeterministic-orchestrator")
        assert items["Orchestrator determinism"]["status"] == "fail"
        assert items["Orchestrator determinism"]["locations"] == [
            {
                "file": "function_app.py",
                "line": 11,
                "message": (
                    "Nondeterministic orchestrator call: "
                    "function_app.py:orchestrator -> random.randint"
                ),
            }
        ]

    def test_multi_trigger_binding_is_intentionally_resolved(self) -> None:
        items = _items_for_example("multi-trigger")
        assert items["Binding connection resolution"]["status"] == "pass"


class TestMonorepoExample:
    """examples/monorepo anchors the SARIF repo-root rebasing contract (#392)."""

    def test_sarif_uris_rebase_onto_the_subdirectory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json as _json

        from typer.testing import CliRunner

        from azure_functions_doctor.cli import cli as app

        runner = CliRunner()
        monkeypatch.chdir(EXAMPLES_DIR.parent / "monorepo")
        result = runner.invoke(app, ["doctor", "--path", "services/api", "--format", "sarif"])
        sarif_results = _json.loads(result.output)["runs"][0]["results"]
        assert sarif_results, "expected findings from the intentionally missing host.json"
        uris = {
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in sarif_results
        }
        # File branch carries the repo-root prefix...
        assert "services/api/host.json" in uris
        # ...and so does the fallback branch; bare names never appear.
        assert "services/api/" in uris
        assert "host.json" not in uris
