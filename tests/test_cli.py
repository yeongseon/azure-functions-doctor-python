import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
from typer.testing import CliRunner

import azure_functions_doctor.cli as cli_module
from azure_functions_doctor.cli import cli as app

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
V2_FIXTURE_PATH = "examples/v2/http-trigger"


def _assert_exit_code_matches_fail_count_text(output: str, exit_code: int) -> None:
    """Parse fail count from human table output summary and validate exit code.

    Summary line format: '  <fail_count> fail(s), <warning_count> warning(s), <passed_count> passed'
    We extract the first '<number> fail' occurrence.
    """
    match = re.search(r"(^|\n)\s*(\d+)\s+fail", output)
    if match:
        fail_count = int(match.group(2))
        expected = 1 if fail_count > 0 else 0
        assert exit_code == expected, (
            f"Expected exit {expected} for {fail_count} fails, got {exit_code}. Output:\n{output}"
        )
    else:
        # If no summary found, keep original expectation of success
        assert exit_code == 0, f"No fail summary found. Output:\n{output}"


def test_cli_table_output() -> None:
    """Test CLI outputs result in table format."""
    result = runner.invoke(app, ["doctor", "--format", "table"])
    _assert_exit_code_matches_fail_count_text(result.output, result.exit_code)
    assert "Azure Functions Doctor" in result.output
    assert any(icon in result.output for icon in ["✓", "✗", "!"])


def test_cli_json_output() -> None:
    """Test JSON output and ensure the exit code matches the fail count."""
    result = runner.invoke(app, ["doctor", "--format", "json"])
    output_text = result.output.strip()
    try:
        data = json.loads(output_text)
    except json.JSONDecodeError as err:
        raise AssertionError("Output is not valid JSON") from err
    assert isinstance(data, dict)
    assert "metadata" in data
    assert "programming_model" in data["metadata"]
    assert "results" in data
    results = data["results"]
    assert isinstance(results, list)
    assert all("title" in section and "items" in section for section in results)
    # Derive fail count from JSON structure
    fail_count = sum(
        1
        for section in results
        for item in section.get("items", [])
        if item.get("status") == "fail"
    )
    expected_exit = 1 if fail_count > 0 else 0
    assert result.exit_code == expected_exit, (
        f"Expected exit {expected_exit} with {fail_count} fails, "
        f"got {result.exit_code}. JSON: {output_text[:500]}"
    )
    assert "programming_model" in data["metadata"]
    assert "target_python" in data["metadata"]


def test_cli_verbose_output() -> None:
    """Test CLI outputs verbose hints when enabled."""
    result = runner.invoke(app, ["doctor", "--format", "table", "--verbose"])
    _assert_exit_code_matches_fail_count_text(result.output, result.exit_code)
    assert "fix:" in result.output  # hint indicator now printed as 'fix:'


def test_cli_sarif_output() -> None:
    """Test CLI outputs SARIF format."""
    result = runner.invoke(app, ["doctor", "--format", "sarif"])
    data = json.loads(result.output)
    assert data.get("version") == "2.1.0"
    assert isinstance(data.get("runs"), list)
    run = data["runs"][0]
    tool = run["tool"]["driver"]
    assert tool["name"] == "azure-functions-doctor"
    assert tool["version"]
    assert run["properties"]["programming_model"]

    has_error = any(item.get("level") == "error" for item in run.get("results", []))
    expected_exit = 1 if has_error else 0
    assert result.exit_code == expected_exit


def test_cli_junit_output() -> None:
    """Test CLI outputs JUnit format."""
    result = runner.invoke(app, ["doctor", "--format", "junit"])
    assert result.output.startswith("<?xml")
    root = ET.fromstring(result.output)
    assert root.tag == "testsuite"
    assert root.attrib.get("name") == "func-doctor"
    tests = int(root.attrib.get("tests", "0"))
    failures = int(root.attrib.get("failures", "0"))
    skipped = int(root.attrib.get("skipped", "0"))
    testcases = root.findall("testcase")
    assert tests == len(testcases)
    assert failures <= tests
    assert skipped <= tests
    assert all(case.attrib.get("classname") for case in testcases)
    assert all(case.attrib.get("name") for case in testcases)
    # warn items must produce <skipped>, not <failure>
    for case in testcases:
        failure_els = case.findall("failure")
        skipped_els = case.findall("skipped")
        msg = "testcase should have at most one status child"
        assert len(failure_els) + len(skipped_els) <= 1, msg
    expected_exit = 1 if failures > 0 else 0
    assert result.exit_code == expected_exit


def test_cli_json_output_includes_programming_model_for_unknown_fixture() -> None:
    """Test JSON output exposes unknown programming model and short-circuit result."""
    result = runner.invoke(
        app,
        ["doctor", "--path", str(FIXTURES_DIR / "unknown"), "--format", "json"],
    )

    data = json.loads(result.output)

    assert result.exit_code == 1
    assert data["metadata"]["programming_model"] == "unknown"
    assert data["results"][0]["category"] == "programming_model"


def test_cli_sarif_output_includes_programming_model_for_unknown_fixture() -> None:
    """Test SARIF output exposes programming model metadata for short-circuit runs."""
    result = runner.invoke(
        app,
        ["doctor", "--path", str(FIXTURES_DIR / "unknown"), "--format", "sarif"],
    )

    data = json.loads(result.output)

    assert result.exit_code == 1
    assert data["runs"][0]["properties"]["programming_model"] == "unknown"


def test_cli_non_v2_projects_fail_with_actionable_message() -> None:
    """Test non-v2 fixtures fail with the expected programming model message."""
    cases = [
        ("v1", "Unsupported programming model: Python v1"),
        ("mixed", "Mixed programming model detected"),
        ("unknown", "Python v2 programming model was not detected"),
    ]

    for fixture_name, expected_message in cases:
        result = runner.invoke(
            app,
            ["doctor", "--path", str(FIXTURES_DIR / fixture_name), "--format", "table"],
        )

        assert result.exit_code == 1
        assert "Programming Model" in result.output
        assert expected_message in result.output


def test_cli_target_python_override_end_to_end() -> None:
    """Test target_python option in table output on a v2 fixture."""
    result = runner.invoke(
        app,
        [
            "doctor",
            "--path",
            V2_FIXTURE_PATH,
            "--target-python",
            "3.12",
        ],
    )
    _assert_exit_code_matches_fail_count_text(result.output, result.exit_code)
    assert "Target Python: 3.12 (override)" in result.output
    assert "Target Python: 3.12 (override) — Tool runtime:" in result.output


def test_cli_target_python_invalid_value() -> None:
    """Test unsupported target_python values fail with supported versions listed."""
    result = runner.invoke(app, ["doctor", "--target-python", "3.99"])
    assert result.exit_code != 0
    assert "Invalid target Python: 3.99" in result.output
    assert "3.99" in result.output
    for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        assert version in result.output


def test_cli_json_output_includes_target_python_override() -> None:
    """Test JSON metadata includes target_python override."""
    result = runner.invoke(
        app,
        [
            "doctor",
            "--path",
            V2_FIXTURE_PATH,
            "--format",
            "json",
            "--target-python",
            "3.11",
        ],
    )
    data = json.loads(result.output)
    assert data["metadata"]["programming_model"] == "v2"
    assert data["metadata"]["target_python"] == "3.11"


def test_cli_sarif_output_includes_target_python_override() -> None:
    """Test SARIF run properties include target_python override."""
    result = runner.invoke(
        app,
        [
            "doctor",
            "--path",
            V2_FIXTURE_PATH,
            "--format",
            "sarif",
            "--target-python",
            "3.11",
        ],
    )
    data = json.loads(result.output)
    assert data["runs"][0]["properties"] == {
        "programming_model": "v2",
        "target_python": "3.11",
    }


def test_write_output_prints_success_message_for_file_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "out.json"
    print_mock = Mock()
    monkeypatch.setattr(cli_module.console, "print", print_mock)

    cli_module._write_output('{"ok": true}', output_path, "JSON")

    assert output_path.read_text(encoding="utf-8") == '{"ok": true}'
    print_mock.assert_called()


def test_validate_inputs_invalid_output_path_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = tmp_path / "project"
    base.mkdir()

    original_resolve = Path.resolve

    def fake_resolve(self: Path, *args: Any, **kwargs: Any) -> Path:
        if str(self).endswith("bad.out"):
            raise OSError("resolve failed")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    result = runner.invoke(app, ["doctor", "--path", str(base), "--output", str(base / "bad.out")])

    assert result.exit_code != 0
    assert "Invalid output path" in result.output


def test_cli_debug_mode_prints_debug_banner() -> None:
    result = runner.invoke(app, ["doctor", "--debug"])
    assert "Debug logging enabled" in result.output
