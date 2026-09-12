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
    assert tool["informationUri"] == "https://github.com/yeongseon/azure-functions-doctor-python"
    assert run["properties"]["programming_model"]

    has_error = any(item.get("level") == "error" for item in run.get("results", []))
    expected_exit = 1 if has_error else 0
    assert result.exit_code == expected_exit


def test_cli_sarif_ruleid_propagates_from_rule_id() -> None:
    """SARIF ``ruleId`` comes from the result's ``rule_id``, matching driver rule ids."""
    result = runner.invoke(
        app,
        ["doctor", "--path", str(FIXTURES_DIR / "unknown"), "--format", "sarif"],
    )
    data = json.loads(result.output)
    run = data["runs"][0]
    driver_ids = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
    findings = run.get("results", [])
    # The unknown fixture short-circuits on programming-model detection, which
    # deterministically yields at least one SARIF finding regardless of the
    # environment or repository state.
    assert findings
    for finding in findings:
        rule_id = finding["ruleId"]
        assert rule_id, "every SARIF finding must carry a ruleId"
        assert rule_id in driver_ids, f"ruleId {rule_id!r} must match a driver rule id"


def test_cli_junit_output() -> None:
    """Test CLI outputs JUnit format."""
    result = runner.invoke(app, ["doctor", "--format", "junit"])
    assert result.output.startswith("<?xml")
    root = ET.fromstring(result.output)
    assert root.tag == "testsuite"
    assert root.attrib.get("name") == "azure-functions-doctor"
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


def test_cli_invalid_deployment_mode() -> None:
    """Unsupported deployment modes fail with the supported values listed."""
    result = runner.invoke(app, ["doctor", "--deployment-mode", "bogus"])
    assert result.exit_code != 0
    assert "Invalid deployment mode: bogus" in result.output
    assert "remote-build" in result.output
    assert "local" in result.output


def test_cli_deployment_mode_local_end_to_end() -> None:
    """A local deployment mode is accepted and recorded in JSON metadata."""
    result = runner.invoke(
        app,
        [
            "doctor",
            "--path",
            V2_FIXTURE_PATH,
            "--format",
            "json",
            "--deployment-mode",
            "local",
        ],
    )
    data = json.loads(result.output)
    assert data["metadata"]["deployment_mode"] == "local"


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
        "deployment_mode": "remote-build",
        "hosting_plan": None,
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

    def fake_resolve(self: Path, strict: bool = False) -> Path:
        if str(self).endswith("bad.out"):
            raise OSError("resolve failed")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    result = runner.invoke(app, ["doctor", "--path", str(base), "--output", str(base / "bad.out")])

    assert result.exit_code != 0
    assert "Invalid output path" in result.output


def test_cli_debug_mode_prints_debug_banner() -> None:
    result = runner.invoke(app, ["doctor", "--debug"])
    assert "Debug logging enabled" in result.output


def test_azure_functions_alias_warns_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deprecated `azure-functions` alias warns on stderr and delegates to cli()."""
    cli_mock = Mock()
    monkeypatch.setattr(cli_module, "cli", cli_mock)

    cli_module.azure_functions_alias()

    cli_mock.assert_called_once_with()
    err = capsys.readouterr().err
    assert "deprecated" in err
    assert "v1.0.0" in err


def test_fdoctor_alias_warns_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Deprecated `fdoctor` alias warns on stderr and delegates to cli()."""
    cli_mock = Mock()
    monkeypatch.setattr(cli_module, "cli", cli_mock)

    cli_module.fdoctor_alias()

    cli_mock.assert_called_once_with()
    err = capsys.readouterr().err
    assert "deprecated" in err
    assert "v1.0.0" in err


def _write_sarif_location_fixture(root: Path) -> int:
    """Create a v2 project that triggers a file-based failure (missing host.json)
    and an AST-based failure (route missing an active @validate_http).

    Returns the 1-based source line of the offending ``handler`` definition.
    """
    (root / "requirements.txt").write_text(
        "azure-functions\nazure-functions-validation\n", encoding="utf-8"
    )
    # @validate_http placed ABOVE @app.route is inactive, so the route emits no
    # endpoint metadata and is flagged by the endpoint_metadata rule.
    source = (
        "import azure.functions as func\n"
        "\n"
        "app = func.FunctionApp()\n"
        "\n"
        "\n"
        "@validate_http\n"
        "@app.route(route='x')\n"
        "def handler(req):\n"
        "    return req\n"
    )
    (root / "function_app.py").write_text(source, encoding="utf-8")
    # 1-based line of `def handler` within the source above.
    return source.splitlines().index("def handler(req):") + 1


def test_cli_sarif_output_emits_per_file_and_per_line_locations(tmp_path: Path) -> None:
    """SARIF results carry per-file locations for a file-based rule and per-line
    "locations (with region) for an AST-based rule.

    Absolute scan roots must never leak into the document: URIs pair with
    %SRCROOT%, so they stay scan-root-relative (issue #392).
    """
    handler_line = _write_sarif_location_fixture(tmp_path)

    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "sarif"])
    data = json.loads(result.output)
    sarif_results = data["runs"][0]["results"]

    def _uri(res: Any) -> str:
        return str(res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"])

    # No absolute filesystem path leaks into any URI.
    assert all(str(tmp_path) not in _uri(r) for r in sarif_results)
    assert all(not _uri(r).startswith("/") for r in sarif_results)

    # File-based rule: missing host.json is reported against the offending file.
    host_json_results = [r for r in sarif_results if _uri(r) == "host.json"]
    assert host_json_results, "expected a SARIF result located at host.json"
    assert "region" not in host_json_results[0]["locations"][0]["physicalLocation"]

    # Rules without a file location collapse to the scan-root-relative root.
    fallback_results = [r for r in sarif_results if _uri(r) == "."]
    assert fallback_results, "expected fallback results located at '.'"

    # AST-based rule: the flagged route carries a per-line region. Filter by
    # ruleId: decorator_order now also emits located function_app.py results.
    ast_results = [
        r
        for r in sarif_results
        if _uri(r) == "function_app.py" and r["ruleId"] == "check_endpoint_metadata"
    ]
    assert ast_results, "expected a SARIF result located at function_app.py"
    region = next(
        r["locations"][0]["physicalLocation"]["region"]
        for r in ast_results
        if "region" in r["locations"][0]["physicalLocation"]
    )
    assert region["startLine"] == handler_line

    # The inverted decorator order is now located too (per-line wiring).
    decorator_results = [r for r in sarif_results if r["ruleId"] == "check_decorator_order"]
    assert decorator_results, "expected located decorator-order findings"
    assert decorator_results[0]["locations"][0]["physicalLocation"]["region"]["startLine"] > 0
    assert region["endLine"] >= region["startLine"]
    assert region["startColumn"] >= 1

    # Every finding carries a stable fingerprint for Code Scanning matching.
    for res in sarif_results:
        fp = res.get("partialFingerprints", {}).get("primaryLocationLineHash")
        assert isinstance(fp, str) and fp


def test_cli_sarif_rebases_relative_scan_root_in_both_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative --path prefixes BOTH branches' URIs (issue #392).

    Monorepo scenario: scanning ``services/api`` must emit
    ``services/api/host.json`` from the file branch AND ``services/api/`` from
    the fallback branch - never a bare ``host.json``.
    """
    services = tmp_path / "services" / "api"
    services.mkdir(parents=True)
    _write_sarif_location_fixture(services)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor", "--path", "services/api", "--format", "sarif"])
    # The fixture intentionally fails required checks (exit 1 is expected).
    sarif_results = json.loads(result.output)["runs"][0]["results"]

    uris = {
        str(r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]) for r in sarif_results
    }
    # File branch keeps the repo-root prefix.
    assert "services/api/host.json" in uris
    assert "services/api/function_app.py" in uris
    # Fallback branch points at the prefixed scan root, not a bare name.
    assert "services/api/" in uris
    assert "host.json" not in uris
    assert "function_app.py" not in uris


def test_create_result_populates_optional_location_fields() -> None:
    """_create_result threads optional file/line/end_line/column when provided."""
    from azure_functions_doctor.handlers._helpers import _create_result

    res = _create_result("fail", "detail", file="function_app.py", line=8, end_line=9, column=1)
    assert res["file"] == "function_app.py"
    assert res["line"] == 8
    assert res["end_line"] == 9
    assert res["column"] == 1

    bare = _create_result("pass", "ok")
    assert "file" not in bare and "line" not in bare


def test_cli_version_flag_prints_package_version() -> None:
    """--version prints the installed version without running a scan (#396)."""
    from azure_functions_doctor import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_cli_doctor_subcommand_still_works_with_version_flag_present(
    tmp_path: Path,
) -> None:
    """Adding the top-level --version callback does not break the subcommand."""
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "json"])
    assert result.exit_code in (0, 1)
    assert result.output.startswith("{")


def test_cli_sarif_emits_one_result_per_finding(tmp_path: Path) -> None:
    """Two uncovered routes yield two located endpoint_metadata results (#395)."""
    (tmp_path / "requirements.txt").write_text(
        "azure-functions==1.25.0\nazure-functions-validation==0.24.0\n", encoding="utf-8"
    )
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from azure_functions_validation import validate_http\n"
        "\n"
        "app = func.FunctionApp()\n"
        "\n"
        "\n"
        "@validate_http\n"
        '@app.route(route="alpha")\n'
        "def alpha(req):\n"
        "    return req\n"
        "\n"
        "\n"
        "@validate_http\n"
        '@app.route(route="beta")\n'
        "def beta(req):\n"
        "    return req\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "sarif"])
    sarif_results = json.loads(result.output)["runs"][0]["results"]
    endpoint = [r for r in sarif_results if r["ruleId"] == "check_endpoint_metadata"]
    assert len(endpoint) == 2, "expected one SARIF result per uncovered route"
    lines = sorted(r["locations"][0]["physicalLocation"]["region"]["startLine"] for r in endpoint)
    assert lines == [9, 15]
    messages = " | ".join(r["message"]["text"] for r in endpoint)
    assert "alpha" in messages and "beta" in messages
    # Distinct fingerprints per finding.
    prints = {r["partialFingerprints"]["primaryLocationLineHash"] for r in endpoint}
    assert len(prints) == 2


def test_cli_sarif_unpinned_requirements_lands_on_lines(tmp_path: Path) -> None:
    """Each unpinned requirement carries its requirements.txt line (#394)."""
    (tmp_path / "requirements.txt").write_text(
        "azure-functions==1.25.0\nrequests>=2.0\nflask\n", encoding="utf-8"
    )
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n\napp = func.FunctionApp()\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "sarif"])
    sarif_results = json.loads(result.output)["runs"][0]["results"]
    unpinned = [r for r in sarif_results if r["ruleId"] == "check_unpinned_requirements"]
    assert unpinned, "expected unpinned-requirements findings"
    lines = sorted(r["locations"][0]["physicalLocation"]["region"]["startLine"] for r in unpinned)
    assert lines == [2, 3]
    uris = {r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in unpinned}
    assert uris == {"requirements.txt"}


def test_normalize_argv_inserts_implicit_doctor_subcommand() -> None:
    """The lone subcommand may be omitted (#399)."""
    from azure_functions_doctor.cli import normalize_argv

    assert normalize_argv([]) == ["doctor"]
    assert normalize_argv(["--path", ".", "--format", "json"]) == [
        "doctor",
        "--path",
        ".",
        "--format",
        "json",
    ]
    assert normalize_argv(["doctor", "--path", "."]) == ["doctor", "--path", "."]
    assert normalize_argv(["--version"]) == ["--version"]
    assert normalize_argv(["--help"]) == ["--help"]
    # Unknown bare words fall through so Typer reports the real error.
    assert normalize_argv(["nonsense"]) == ["nonsense"]


def test_cli_top_level_invocation_matches_subcommand(tmp_path: Path) -> None:
    """`--path X --format json` and `doctor --path X --format json` agree (#399)."""
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n\napp = func.FunctionApp()\n", encoding="utf-8"
    )
    from azure_functions_doctor.cli import normalize_argv

    with_sub = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--format", "json"])
    without_sub = runner.invoke(app, normalize_argv(["--path", str(tmp_path), "--format", "json"]))
    assert with_sub.exit_code == without_sub.exit_code
    assert json.loads(without_sub.output)["schema_version"] == "2.0"
