"""Golden CLI compatibility with origin/main 89cf15d.

Baseline generation: git worktree add --detach /tmp/opencode/doctor-624-main
origin/main; run this fixture's project with the same interpreter and PYTHONPATH
pointing at that worktree's src. Capture native JSON and SARIF results verbatim
in fixtures/native-main.json; requirements-main.b64 is the zlib/base64-encoded
full table/JSON/SARIF capture plus selected rules (native and unpinned). Only
generated_at, the temporary root and tool-version metadata are normalized. No main code is imported
at test time. Other gap-sensitive rules are compared by the worktree probe.
"""

import base64
import json
from pathlib import Path
import re
import zlib

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli


def _normalize_tool_version(output: str) -> str:
    """Replace known report metadata only, without reserializing golden bytes."""
    return re.sub(
        r'("metadata"\s*:\s*\{\s*"tool_version"\s*:\s*"|'
        r'"tool"\s*:\s*\{\s*"driver"\s*:\s*\{\s*'
        r'"name"\s*:\s*"azure-functions-doctor"\s*,\s*"version"\s*:\s*")'
        r'[^"\n]+(")',
        r"\1<VERSION>\2",
        output,
    )


@pytest.mark.parametrize("output", ["json", "sarif"])
def test_golden_comparison_ignores_tool_version(output: str) -> None:
    # Given a saved report and a release changing only its tool metadata.
    baseline = json.loads(
        zlib.decompress(
            base64.b64decode((Path(__file__).parent / "fixtures/requirements-main.b64").read_text())
        )
    )
    expected = baseline["formats"][output]["output"]
    actual = expected.replace('"tool_version": "0.23.1"', '"tool_version": "9.8.7"')
    actual = actual.replace('"version": "0.23.1"', '"version": "9.8.7"')
    assert actual != expected
    # When both sides use the same byte-preserving normalization.
    normalized = _normalize_tool_version(actual)
    # Then a tool-version bump is not a diagnostic regression.
    assert normalized == _normalize_tool_version(expected)


@pytest.mark.parametrize("output", ["json", "sarif"])
@pytest.mark.parametrize("change", ["finding", "gate", "schema", "formatting"])
def test_golden_comparison_detects_report_changes(output: str, change: str) -> None:
    # Given a golden report with a semantic or formatting regression.
    baseline = json.loads(
        zlib.decompress(
            base64.b64decode((Path(__file__).parent / "fixtures/requirements-main.b64").read_text())
        )
    )
    expected = baseline["formats"][output]["output"]
    replacements = {
        "finding": ('"check_native_dependency_risk"', '"changed_finding"'),
        "gate": ('"gate_failed": false', '"gate_failed": true'),
        "schema": ('"2.0"', '"99.0"') if output == "json" else ('"2.1.0"', '"99.0"'),
        "formatting": ('\n  "', '\n   "'),
    }
    actual = expected.replace(*replacements[change])
    assert actual != expected
    # When tool-version metadata is normalized on both sides.
    normalized = _normalize_tool_version(actual)
    # Then the report change still fails the golden byte comparison.
    assert normalized != _normalize_tool_version(expected)


@pytest.mark.parametrize("output", ["json", "sarif"])
def test_no_gap_native_output_matches_captured_main(tmp_path: Path, output: str) -> None:
    (tmp_path / "requirements.txt").write_text(
        "azure-functions==1.25.0\n-r local.txt\n-c constraints.txt\n"
    )
    (tmp_path / "local.txt").write_text("# local dependencies\nnumpy\nrequests\n")
    (tmp_path / "constraints.txt").write_text("pandas\n")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n"
    )
    (tmp_path / "host.json").write_text('{"version":"2.0"}')
    result = CliRunner().invoke(cli, ["doctor", "--path", str(tmp_path), "--format", output])
    assert result.exit_code == 0
    data = json.loads(result.output)
    baseline = json.loads((Path(__file__).parent / "fixtures/native-main.json").read_text())
    if output == "json":
        native = next(
            i
            for s in data["results"]
            for i in s["items"]
            if i["rule_id"] == "check_native_dependency_risk"
        )
    else:
        native = next(
            i for i in data["runs"][0]["results"] if i["ruleId"] == "check_native_dependency_risk"
        )
    assert native == baseline[output]


@pytest.mark.parametrize("output", ["table", "json", "sarif"])
def test_complete_dependency_reports_match_main(
    tmp_path: Path, output: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = json.loads(
        zlib.decompress(
            base64.b64decode((Path(__file__).parent / "fixtures/requirements-main.b64").read_text())
        )
    )
    (tmp_path / "requirements.txt").write_text(
        "azure-functions==1.25.0\n-r local.txt\n-c constraints.txt\n"
    )
    (tmp_path / "local.txt").write_text("# local dependencies\nnumpy\nrequests\n")
    (tmp_path / "constraints.txt").write_text("pandas\n")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n"
    )
    (tmp_path / "host.json").write_text('{"version":"2.0"}')
    (tmp_path / "rules.json").write_text(json.dumps(baseline["rules"]))
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("NO_COLOR", "1")
    result = CliRunner().invoke(
        cli,
        [
            "doctor",
            "--path",
            str(tmp_path),
            "--rules",
            str(tmp_path / "rules.json"),
            "--format",
            output,
        ],
    )
    normalized = re.sub(
        r'"generated_at": "[^"]+"', '"generated_at": "TIMESTAMP"', result.output
    ).replace(str(tmp_path), "PROJECT_ROOT")
    assert result.exit_code == baseline["formats"][output]["exit_code"]
    assert _normalize_tool_version(normalized) == _normalize_tool_version(
        baseline["formats"][output]["output"]
    )
