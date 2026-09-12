"""Finding Contract schema validation and exit-code regression (issue #411).

The prose contract in docs/json_output_contract.md now has a machine-readable
counterpart (schemas/output-contract-2.0.schema.json, shipped in the wheel).
These tests pin the contract end to end:

- Representative skip/warn/fail findings validate against the schema.
- Evidence fields, per-finding ``locations``, and the deterministic analysis
  marker round-trip through the CLI.
- Exit-code semantics regress: 0 when required checks pass, 1 on any required
  failure, unchanged by optional warns.
- Location fields stay scan-root-relative (never absolute paths).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli as app

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = (
    REPO_ROOT / "src" / "azure_functions_doctor" / "schemas" / "output-contract-2.0.schema.json"
)


@pytest.fixture(scope="module")
def contract_schema() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return data


def _doctor_json(path: Path, profile: str | None = None) -> tuple[int, dict[str, Any]]:
    args = ["doctor", "--path", str(path), "--format", "json"]
    if profile:
        args += ["--profile", profile]
    result = runner.invoke(app, args)
    return result.exit_code, json.loads(result.output)


def _write_warn_fixture(tmp_path: Path) -> None:
    """A project whose findings exercise warn + evidence + locations paths."""
    (tmp_path / "requirements.txt").write_text(
        "azure-functions==1.25.0\nrequests>=2.0\n", encoding="utf-8"
    )
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n\napp = func.FunctionApp()\n", encoding="utf-8"
    )
    (tmp_path / "host.json").write_text('{"version": "2.0"}', encoding="utf-8")


class TestSchemaConformance:
    def test_schema_file_ships_in_the_package(self) -> None:
        import azure_functions_doctor.schemas as schemas_pkg

        shipped = Path(schemas_pkg.__file__).parent / "output-contract-2.0.schema.json"
        assert shipped.exists(), "schema must ship as package data"

    def test_healthy_example_validates(self, contract_schema: dict[str, Any]) -> None:
        from jsonschema import Draft7Validator

        exit_code, data = _doctor_json(REPO_ROOT / "examples" / "v2" / "http-trigger")
        assert exit_code == 0
        Draft7Validator.check_schema(contract_schema)
        errors = list(Draft7Validator(contract_schema).iter_errors(data))
        assert not errors, "\n".join(e.message for e in errors)

    def test_warn_fixture_with_locations_and_evidence_validates(
        self, contract_schema: dict[str, Any], tmp_path: Path
    ) -> None:
        from jsonschema import Draft7Validator

        _write_warn_fixture(tmp_path)
        exit_code, data = _doctor_json(tmp_path, profile="full")
        assert exit_code == 0  # warns only; nothing required fails

        items = [i for s in data["results"] for i in s["items"]]
        statuses = {i["status"] for i in items}
        assert "warn" in statuses

        errors = list(Draft7Validator(contract_schema).iter_errors(data))
        assert not errors, "\n".join(e.message for e in errors)

        # Finding Contract v2 round-trip: lifecycle findings carry evidence
        # provenance and the deterministic marker.
        lifecycle = next(i for i in items if i["rule_id"] == "check_python_runtime_lifecycle")
        assert lifecycle["analysis"]["type"] == "deterministic"
        assert lifecycle["source_url"].startswith("https://")
        assert lifecycle["last_verified"]

        # Per-finding locations round-trip: unpinned requirements carry lines.
        unpinned = [i for i in items if i["rule_id"] == "check_unpinned_requirements"]
        assert unpinned and unpinned[0]["locations"], "expected located findings"
        assert unpinned[0]["locations"][0]["file"] == "requirements.txt"

    def test_broken_example_validates_with_fail_status(
        self, contract_schema: dict[str, Any], tmp_path: Path
    ) -> None:
        from jsonschema import Draft7Validator

        exit_code, data = _doctor_json(REPO_ROOT / "examples" / "v2" / "broken-missing-host-json")
        assert exit_code == 1
        errors = list(Draft7Validator(contract_schema).iter_errors(data))
        assert not errors, "\n".join(e.message for e in errors)

        items = [i for s in data["results"] for i in s["items"]]
        assert any(i["status"] == "fail" for i in items)

    def test_location_fields_never_absolute(self, tmp_path: Path) -> None:
        _write_warn_fixture(tmp_path)
        _exit, data = _doctor_json(tmp_path, profile="full")
        items = [i for s in data["results"] for i in s["items"]]
        for item in items:
            if item.get("file"):
                assert not str(item["file"]).startswith("/"), item["file"]
            for loc in item.get("locations", []) or []:
                assert not str(loc.get("file", "")).startswith("/"), loc


class TestExitCodeSemantics:
    def test_pass_exits_zero(self) -> None:
        exit_code, _ = _doctor_json(REPO_ROOT / "examples" / "v2" / "http-trigger")
        assert exit_code == 0

    def test_required_failure_exits_one(self) -> None:
        exit_code, _ = _doctor_json(REPO_ROOT / "examples" / "v2" / "broken-missing-host-json")
        assert exit_code == 1

    def test_optional_warns_do_not_gate(self, tmp_path: Path) -> None:
        """Warns (unpinned requirements, app insights) keep the exit code 0."""
        _write_warn_fixture(tmp_path)
        exit_code, data = _doctor_json(tmp_path, profile="full")
        assert exit_code == 0
        items = [i for s in data["results"] for i in s["items"]]
        assert any(i["status"] == "warn" for i in items)
