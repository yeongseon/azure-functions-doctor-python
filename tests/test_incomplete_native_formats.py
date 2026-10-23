import json
from pathlib import Path

from jsonschema import validate
import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli


@pytest.mark.parametrize("output", ["table", "json", "sarif"])
def test_native_finding_and_gap_survive_all_formats(tmp_path: Path, output: str) -> None:
    root = tmp_path / "app"
    root.mkdir()
    (tmp_path / "common.txt").write_text("OUTSIDE_CANARY\n")
    (root / "requirements.txt").write_text("azure-functions\nnumpy\n-r ../common.txt\n")
    (root / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n"
    )
    (root / "host.json").write_text('{"version":"2.0"}')
    result = CliRunner().invoke(cli, ["doctor", "--path", str(root), "--format", output])
    assert result.exit_code == 0, result.output
    assert "OUTSIDE_CANARY" not in result.output
    if output == "table":
        assert "Native dependencies detected: numpy" in result.output
        assert "not inspected" in result.output
    elif output == "json":
        data = json.loads(result.output)
        native = next(
            i
            for s in data["results"]
            for i in s["items"]
            if i["rule_id"] == "check_native_dependency_risk"
        )
        assert "numpy" in native["value"]
        assert "not inspected" in native["value"]
        assert len(native["locations"]) == 2
    else:
        data = json.loads(result.output)
        assert data["version"] == "2.1.0"
        validate(
            data,
            {
                "type": "object",
                "required": ["version", "runs"],
                "properties": {
                    "version": {"const": "2.1.0"},
                    "runs": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["tool", "results"],
                            "properties": {
                                "results": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["ruleId", "message", "locations"],
                                        "properties": {
                                            "message": {"type": "object", "required": ["text"]},
                                            "locations": {"type": "array", "minItems": 1},
                                        },
                                    },
                                }
                            },
                        },
                    },
                },
            },
        )
        native = [
            r for r in data["runs"][0]["results"] if r["ruleId"] == "check_native_dependency_risk"
        ]
        assert len(native) == 2
        assert sum("numpy" in r["message"]["text"] for r in native) == 1
        assert sum("not inspected" in r["message"]["text"] for r in native) == 1
        assert [r["locations"][0]["physicalLocation"]["region"]["startLine"] for r in native] == [
            2,
            3,
        ]
