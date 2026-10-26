import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli


@pytest.mark.parametrize("output_format", ["table", "json", "sarif"])
@pytest.mark.parametrize("layout", ["root", "child", "crlf"])
def test_bom_does_not_hide_requirements_includes(
    tmp_path: Path, output_format: str, layout: str
) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n", encoding="utf-8"
    )
    (tmp_path / "host.json").write_text('{"version":"2.0"}', encoding="utf-8")
    newline = "\r\n" if layout == "crlf" else "\n"
    root = "-r child.txt" + newline
    child = "-r packages.txt" + newline
    if layout in {"root", "crlf"}:
        root = "\ufeff" + root
    else:
        child = "\ufeff" + child
    (tmp_path / "requirements.txt").write_bytes(root.encode())
    (tmp_path / "child.txt").write_bytes(child.encode())
    (tmp_path / "packages.txt").write_text("azure-functions==1.21.3\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli, ["doctor", "--path", str(tmp_path), "--profile", "minimal", "--format", output_format]
    )

    assert result.exit_code == 0, result.output
    if output_format == "json":
        report = json.loads(result.stdout)
        findings = [item for section in report["results"] for item in section["items"]]
        assert (
            next(item for item in findings if item["rule_id"] == "check_azure_functions_library")[
                "status"
            ]
            == "pass"
        )
    elif output_format == "sarif":
        report = json.loads(result.stdout)
        assert not any(
            item["ruleId"] == "check_azure_functions_library"
            for item in report["runs"][0]["results"]
        )
