import json
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli as app
from azure_functions_doctor.handlers.registry import HandlerRegistry


def test_flattened_consumer_reports_incomplete_include(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("azure-functions\n-c ../constraints.txt\n")
    result = HandlerRegistry().handle(
        {"type": "package_declared", "condition": {"package": "azure-functions"}}, tmp_path
    )
    assert result["severity"] == "warning"
    assert result["gate"] is False
    assert result["line"] == 2


def test_inside_include_keeps_normal_inspection(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("-r common.txt\n")
    (tmp_path / "common.txt").write_text("numpy\n")
    result = HandlerRegistry().handle({"type": "native_dependency_risk"}, tmp_path)
    assert result["status"] == "fail"
    assert "numpy" in result["detail"]
    assert "incomplete" not in result["detail"]


def test_cli_reports_advisory_incomplete_inspection_with_v2_contract(tmp_path: Path) -> None:
    root = tmp_path / "app"
    root.mkdir()
    (tmp_path / "common.txt").write_text("numpy\n")
    (root / "requirements.txt").write_text("azure-functions\n-r ../common.txt\n")
    (root / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n"
    )
    (root / "host.json").write_text('{"version":"2.0"}')
    result = CliRunner().invoke(
        app, ["doctor", "--path", str(root), "--profile", "minimal", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["schema_version"] == "2.0"
    finding = next(
        item
        for section in data["results"]
        for item in section["items"]
        if item["rule_id"] == "check_azure_functions_library"
    )
    assert finding["status"] == "warn"
    assert finding["severity"] == "warning"
    assert finding["file"] == "requirements.txt" and finding["line"] == 2
    assert "../common.txt" in finding["value"]
    assert str(tmp_path / "common.txt") not in finding["value"]
    schema = (
        Path(__file__).resolve().parents[1]
        / "src/azure_functions_doctor/schemas/output-contract-2.0.schema.json"
    )
    jsonschema.validate(data, json.loads(schema.read_text()))


@pytest.mark.parametrize("directive", ["-r", "-c", "--requirement=", "--constraint="])
def test_flattened_consumer_retains_written_reference_and_location(
    tmp_path: Path, directive: str
) -> None:
    from azure_functions_doctor.handlers._helpers import _iter_requirements_txt_lines
    from azure_functions_doctor.inspection_gaps import collect_inspection_gaps

    reference = "../CANARY_PATH.txt"
    content = f"azure-functions\n{directive} {reference}\n"
    with collect_inspection_gaps() as gaps:
        lines = _iter_requirements_txt_lines(content, tmp_path / "requirements.txt")
    assert lines == ["azure-functions"]
    assert [(gap.reference, gap.line) for gap in gaps] == [(reference, 2)]


def test_discovered_outside_link_is_advisory_and_inside_link_is_followed(tmp_path: Path) -> None:
    from azure_functions_doctor.handlers._helpers import iter_project_files
    from azure_functions_doctor.inspection_gaps import collect_inspection_gaps

    root = tmp_path / "app"
    root.mkdir()
    (tmp_path / "outside.py").write_text("CANARY_OUTSIDE")
    (root / "outside.py").symlink_to(tmp_path / "outside.py")
    (root / "inside.py").write_text("app = 1")
    (root / "alias.py").symlink_to(root / "inside.py")
    with collect_inspection_gaps() as gaps:
        discovered = list(iter_project_files(root, "*.py"))
    assert root / "alias.py" in discovered
    assert root / "outside.py" not in discovered
    assert [gap.reference for gap in gaps] == ["outside.py"]


def test_inside_symlink_include_is_visibly_refused(tmp_path: Path) -> None:
    (tmp_path / "common.txt").write_text("numpy\n")
    (tmp_path / "alias.txt").symlink_to(tmp_path / "common.txt")
    (tmp_path / "requirements.txt").write_text("-r alias.txt\n")
    result = HandlerRegistry().handle({"type": "native_dependency_risk"}, tmp_path)
    assert "numpy" not in result["detail"]
    assert "incomplete" in result["detail"]


def test_known_dependency_finding_survives_incomplete_include(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("numpy\n-r ../common.txt\n")
    result = HandlerRegistry().handle({"type": "native_dependency_risk"}, tmp_path)
    assert "numpy" in result["detail"]
    assert "incomplete" in result["detail"]


def test_gap_collection_does_not_leak_between_rules(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("-r ../common.txt\n")
    registry = HandlerRegistry()
    registry.handle({"type": "native_dependency_risk"}, tmp_path)
    result = registry.handle(
        {"type": "file_exists", "condition": {"target": "requirements.txt"}}, tmp_path
    )
    assert result["status"] == "pass"
    assert "incomplete" not in result["detail"]
