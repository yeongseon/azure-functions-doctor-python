import json
from pathlib import Path
import sys
import tempfile
from typing import cast

from pytest import MonkeyPatch

from azure_functions_doctor.handlers import (
    Condition,
    Rule,
    _collect_blueprint_aliases,
    _collect_register_functions_args,
    _create_result,
    _detect_native_dependency_risks,
    _handle_exception,
    _source_contains_blueprint_decorator,
    generic_handler,
)


def test_compare_python_version_pass() -> None:
    """Test that the Python version check passes for the current version."""
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": ">=",
            "value": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "pass"
    assert "tool runtime" in result["detail"]


def test_compare_python_version_fail() -> None:
    """Test that the Python version check fails for an unsupported version."""
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": ">",
            "value": "99.0",
        },
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "fail"


def test_compare_python_version_override_pass() -> None:
    """Test that target_python override is used for version comparison."""
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": "==",
            "value": "3.12",
        },
    }
    result = generic_handler(rule, Path("."), {"target_python": "3.12"})
    assert result["status"] == "pass"
    assert result["detail"].startswith("Target Python: 3.12 (override)")


def test_compare_python_version_override_fail() -> None:
    """Test that mismatched target_python override fails the rule."""
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": "==",
            "value": "3.13",
        },
    }
    result = generic_handler(rule, Path("."), {"target_python": "3.10"})
    assert result["status"] == "fail"
    assert "Tool runtime:" in result["detail"]


def test_compare_func_core_tools_version_pass(monkeypatch: MonkeyPatch) -> None:
    """Test that the func Core Tools version check passes when version meets minimum."""
    from azure_functions_doctor import handlers

    monkeypatch.setattr(
        handlers, "resolve_target_value", lambda t: "4.0.5455" if t == "func_core_tools" else ""
    )
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "func_core_tools",
            "operator": ">=",
            "value": "4.0",
        },
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "pass"
    assert "4.0.5455" in result.get("detail", "")


def test_compare_func_core_tools_version_fail_not_installed(monkeypatch: MonkeyPatch) -> None:
    """Test that the func Core Tools version check fails when func is not installed."""
    from azure_functions_doctor import handlers

    monkeypatch.setattr(
        handlers,
        "resolve_target_value",
        lambda t: "not_installed" if t == "func_core_tools" else "",
    )
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "func_core_tools",
            "operator": ">=",
            "value": "4.0",
        },
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "fail"
    assert "not_installed" in result.get("detail", "")


def test_compare_func_core_tools_version_fail_old_version(monkeypatch: MonkeyPatch) -> None:
    """Test that the func Core Tools version check fails when version is below minimum."""
    from azure_functions_doctor import handlers

    monkeypatch.setattr(
        handlers, "resolve_target_value", lambda t: "3.0.0" if t == "func_core_tools" else ""
    )
    rule: Rule = {
        "type": "compare_version",
        "condition": {
            "target": "func_core_tools",
            "operator": ">=",
            "value": "4.0",
        },
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "fail"
    assert "3.0.0" in result.get("detail", "")


def test_env_var_exists_pass(monkeypatch: MonkeyPatch) -> None:
    """ "Test that the environment variable check passes when the variable is set."""
    monkeypatch.setenv("MY_ENV_VAR", "true")
    rule: Rule = {
        "type": "env_var_exists",
        "condition": {"target": "MY_ENV_VAR"},
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "pass"


def test_env_var_exists_fail(monkeypatch: MonkeyPatch) -> None:
    """Test that the environment variable check fails when the variable is not set."""
    monkeypatch.delenv("MY_ENV_VAR", raising=False)
    rule: Rule = {
        "type": "env_var_exists",
        "condition": {"target": "MY_ENV_VAR"},
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "fail"


def test_path_exists_pass() -> None:
    """Test that the path exists check passes for sys.executable."""
    rule: Rule = {
        "type": "path_exists",
        "condition": {"target": "sys.executable"},
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "pass"


def test_file_exists_pass() -> None:
    """Test that the file exists check passes when the file is present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.txt"
        file_path.write_text("test")
        rule: Rule = {
            "type": "file_exists",
            "condition": {"target": "test.txt"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "pass"


def test_file_exists_fail() -> None:
    """Test that the file exists check fails when the file is not present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rule: Rule = {
            "type": "file_exists",
            "condition": {"target": "not_found.txt"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "fail"


def test_package_installed_pass() -> None:
    """Test that the package installed check passes for an existing package."""
    rule: Rule = {
        "type": "package_installed",
        "condition": {"target": "os"},
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "pass"


def test_package_installed_fail() -> None:
    rule: Rule = {
        "type": "package_installed",
        "condition": {"target": "nonexistent_package_zzz"},
    }
    result = generic_handler(rule, Path("."))
    assert result["status"] == "fail"


def test_source_code_contains_pass() -> None:
    """Test that the source code contains check passes when the keyword is found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "sample.py"
        file_path.write_text("# keyword: found")
        rule: Rule = {
            "type": "source_code_contains",
            "condition": {"keyword": "keyword"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "pass"


def test_source_code_contains_fail() -> None:
    """Test that the source code contains check fails when the keyword is not found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "sample.py"
        file_path.write_text("# no match here")
        rule: Rule = {
            "type": "source_code_contains",
            "condition": {"keyword": "notfound"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "fail"


def test_source_code_contains_ast_pass() -> None:
    """Test that AST mode passes when decorator @app.xxx is present in source."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "app.py"
        file_path.write_text(
            "from azure.functions import FunctionApp\n"
            "app = FunctionApp()\n\n"
            "@app.route()\n"
            "def main(req):\n"
            "    return 'ok'\n"
        )
        rule: Rule = {
            "type": "source_code_contains",
            "condition": {"keyword": "@app.", "mode": "ast"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "pass"
        assert "AST" in result.get("detail", "")


def test_source_code_contains_ast_fail() -> None:
    """Test that AST mode fails when keyword appears only in comment (no real decorator)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "app.py"
        file_path.write_text("# We use @app. decorators elsewhere\nx = 1\n")
        rule: Rule = {
            "type": "source_code_contains",
            "condition": {"keyword": "@app.", "mode": "ast"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "fail"
        assert "AST" in result.get("detail", "")


def test_unknown_check_type() -> None:
    """Test that an unknown check type returns a fail status."""
    rule = cast(
        Rule,
        cast(
            object,
            {
                "type": "unknown_type",
                "id": "invalid_type",
                "label": "Invalid check",
                "section": "misc",
                "category": "misc",
                "condition": {"target": "anything"},
            },
        ),
    )

    result = generic_handler(rule, Path("."))

    assert result["status"] == "fail"
    assert "Unknown check type" in result["detail"]


def test_conditional_exists_no_durable_usage_pass() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # No durable usage in source -> check should be skipped/pass
        rule: Rule = {
            "type": "conditional_exists",
            "condition": {"jsonpath": "$.extensions.durableTask"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "pass"


def test_conditional_exists_durable_missing_host_fail() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python file that contains durable keyword
        file_path = Path(tmpdir) / "function.py"
        file_path.write_text(
            "# uses durable\nfrom azure.durable_functions import DurableOrchestrationContext"
        )

        rule: Rule = {
            "type": "conditional_exists",
            "condition": {"jsonpath": "$.extensions.durableTask"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "fail"


def test_conditional_exists_durable_present_pass() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a Python file that contains durable keyword
        file_path = Path(tmpdir) / "function.py"
        file_path.write_text(
            "# uses durable\nfrom azure.durable_functions import DurableOrchestrationContext"
        )
        # Create host.json with the durableTask entry
        host = Path(tmpdir) / "host.json"
        host.write_text('{"extensions": {"durableTask": {}}}')

        rule: Rule = {
            "type": "conditional_exists",
            "condition": {"jsonpath": "$.extensions.durableTask"},
        }
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "pass"


def test_callable_detection_pass_and_fail() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # No ASGI/WSGI files => fail
        rule: Rule = {"type": "callable_detection"}
        result = generic_handler(rule, Path(tmpdir))
        assert result["status"] == "fail"

        # Add a FastAPI example => pass
        file_path = Path(tmpdir) / "app.py"
        file_path.write_text("from fastapi import FastAPI\napp = FastAPI()")
        result2 = generic_handler(rule, Path(tmpdir))
        assert result2["status"] == "pass"


def _make_rule(rule_type: str, condition: Condition) -> Rule:
    # Helper to build a Rule object for new adapter handlers (partial Rule)
    return cast(Rule, cast(object, {"type": rule_type, "condition": condition}))


def test_executable_exists_pass_and_fail(tmp_path: Path) -> None:
    # 'sh' should exist on most Unix systems
    rule = _make_rule("executable_exists", {"target": "sh"})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"

    rule_fail = _make_rule("executable_exists", {"target": "definitely_not_present_abc123"})
    res2 = generic_handler(rule_fail, tmp_path)
    assert res2["status"] == "fail"


def test_any_of_exists_env_and_file(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    # env var path
    monkeypatch.setenv("AZFUNC_TEST_VAR", "1")
    rule = _make_rule("any_of_exists", {"targets": ["AZFUNC_TEST_VAR"]})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"

    # file path
    f = tmp_path / "marker.txt"
    f.write_text("ok")
    rule_file = _make_rule("any_of_exists", {"targets": [str(f.name)]})
    res2 = generic_handler(rule_file, tmp_path)
    assert res2["status"] == "pass"

    # none exist
    rule_none = _make_rule("any_of_exists", {"targets": ["nope1", "nope2"]})
    res3 = generic_handler(rule_none, tmp_path)
    assert res3["status"] == "fail"


def test_file_glob_check(tmp_path: Path) -> None:
    # create an unwanted file matching pattern
    bad = tmp_path / "secret.txt"
    bad.write_text("secret")
    rule = _make_rule("file_glob_check", {"patterns": ["secret.txt"]})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"

    # no matches
    rule_ok = _make_rule("file_glob_check", {"patterns": ["*.doesnotexist"]})
    res2 = generic_handler(rule_ok, tmp_path)
    assert res2["status"] == "pass"


def test_host_json_property_pass_and_fail(tmp_path: Path) -> None:
    host = tmp_path / "host.json"
    host.write_text(json.dumps({"extensionBundle": {"id": "bundle"}}))
    rule = _make_rule("host_json_property", {"jsonpath": "$.extensionBundle"})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"

    # missing property
    host.write_text(json.dumps({}))
    res2 = generic_handler(rule, tmp_path)
    assert res2["status"] == "fail"


def test_package_installed_uses_find_spec_no_side_effects() -> None:
    """Test that package_installed uses importlib.util.find_spec (no import side-effects)."""
    import importlib.util
    from unittest.mock import patch

    call_log: list[str | None] = []

    original_find_spec = importlib.util.find_spec

    def spy_find_spec(name: str | None, *args: object, **kwargs: object) -> object:
        call_log.append(name)
        if name is None:
            return None
        return original_find_spec(name)

    with patch("importlib.util.find_spec", side_effect=spy_find_spec):
        rule: Rule = {
            "type": "package_installed",
            "condition": {"target": "os"},
        }
        result = generic_handler(rule, Path("."))

    assert result["status"] == "pass"
    assert "os" in call_log


def test_host_json_version_pass(tmp_path: Path) -> None:
    """Test host_json_version passes when host.json has version 2.0."""
    host = tmp_path / "host.json"
    host.write_text('{"version": "2.0", "extensionBundle": {}}')
    rule = _make_rule("host_json_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"
    assert '"2.0"' in res.get("detail", "")


def test_host_json_version_fail_wrong_version(tmp_path: Path) -> None:
    """Test host_json_version fails when host.json has wrong version."""
    host = tmp_path / "host.json"
    host.write_text('{"version": "1.0"}')
    rule = _make_rule("host_json_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "1.0" in res.get("detail", "")


def test_host_json_version_fail_missing_version(tmp_path: Path) -> None:
    """Test host_json_version fails when host.json lacks the version field."""
    host = tmp_path / "host.json"
    host.write_text('{"extensionBundle": {}}')
    rule = _make_rule("host_json_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"


def test_host_json_version_fail_missing_file(tmp_path: Path) -> None:
    """Test host_json_version fails when host.json is absent."""
    rule = _make_rule("host_json_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "not found" in res.get("detail", "")


def test_host_json_version_fail_invalid_json(tmp_path: Path) -> None:
    """Test host_json_version fails gracefully when host.json is not valid JSON."""
    host = tmp_path / "host.json"
    host.write_text("this is not json {{{")
    rule = _make_rule("host_json_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"


def test_local_settings_security_not_present(tmp_path: Path) -> None:
    """Test local_settings_security passes when local.settings.json does not exist."""
    rule = _make_rule("local_settings_security", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"
    assert "not present" in res.get("detail", "").lower()


def test_local_settings_security_not_tracked(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Test local_settings_security passes when local.settings.json is not git-tracked."""
    import subprocess as _subprocess

    settings = tmp_path / "local.settings.json"
    settings.write_text('{"IsEncrypted": false}')

    # Simulate git ls-files returning non-zero (file not tracked)
    def fake_run(cmd: list[str], **kwargs: object) -> object:
        class FakeResult:
            returncode = 1

        return FakeResult()

    monkeypatch.setattr(_subprocess, "run", fake_run)
    rule = _make_rule("local_settings_security", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"
    assert "not tracked" in res.get("detail", "").lower()


def test_local_settings_security_tracked(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Test local_settings_security fails when local.settings.json is git-tracked."""
    import subprocess as _subprocess

    settings = tmp_path / "local.settings.json"
    settings.write_text('{"IsEncrypted": false}')

    # Simulate git ls-files returning zero (file is tracked)
    def fake_run(cmd: list[str], **kwargs: object) -> object:
        class FakeResult:
            returncode = 0

        return FakeResult()

    monkeypatch.setattr(_subprocess, "run", fake_run)
    rule = _make_rule("local_settings_security", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert ".gitignore" in res.get("detail", "")


def test_local_settings_security_git_not_available(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Test local_settings_security passes gracefully when git is unavailable."""
    import subprocess as _subprocess

    settings = tmp_path / "local.settings.json"
    settings.write_text('{"IsEncrypted": false}')

    def fake_run(cmd: list[str], **kwargs: object) -> None:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(_subprocess, "run", fake_run)
    rule = _make_rule("local_settings_security", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"
    assert "skipped" in res.get("detail", "").lower()


def test_extension_bundle_v4_pass(tmp_path: Path) -> None:
    """Test host_json_extension_bundle_version passes for a valid v4 bundle range."""
    host = tmp_path / "host.json"
    host.write_text(
        '{"version": "2.0", "extensionBundle": '
        '{"id": "Microsoft.Azure.Functions.ExtensionBundle", "version": "[4.*, 5.0.0)"}}'
    )
    rule = _make_rule("host_json_extension_bundle_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"
    assert "4" in res.get("detail", "")


def test_extension_bundle_v4_fail_old_version(tmp_path: Path) -> None:
    """Test host_json_extension_bundle_version fails for a v3 bundle range."""
    host = tmp_path / "host.json"
    host.write_text(
        '{"version": "2.0", "extensionBundle": '
        '{"id": "Microsoft.Azure.Functions.ExtensionBundle", "version": "[3.*, 4.0.0)"}}'
    )
    rule = _make_rule("host_json_extension_bundle_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "below" in res.get("detail", "").lower() or "v4" in res.get("detail", "").lower()


def test_extension_bundle_v4_fail_missing_bundle(tmp_path: Path) -> None:
    """Test host_json_extension_bundle_version fails when extensionBundle is absent."""
    host = tmp_path / "host.json"
    host.write_text('{"version": "2.0"}')
    rule = _make_rule("host_json_extension_bundle_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    detail = res.get("detail", "").lower()
    assert "extensionbundle" in detail or "extension" in detail


def test_extension_bundle_v4_fail_wrong_id(tmp_path: Path) -> None:
    """Test host_json_extension_bundle_version fails when bundle id is not the recommended one."""
    host = tmp_path / "host.json"
    host.write_text(
        '{"version": "2.0", "extensionBundle": {"id": "Custom.Bundle", "version": "[4.*, 5.0.0)"}}'
    )
    rule = _make_rule("host_json_extension_bundle_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "Custom.Bundle" in res.get("detail", "")


def test_extension_bundle_v4_fail_missing_host_json(tmp_path: Path) -> None:
    """Test host_json_extension_bundle_version fails when host.json is absent."""
    rule = _make_rule("host_json_extension_bundle_version", {})
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "not found" in res.get("detail", "").lower()


def test_package_forbidden_pass(tmp_path: Path) -> None:
    """package_forbidden passes when the forbidden package is NOT in requirements.txt."""
    req = tmp_path / "requirements.txt"
    req.write_text("azure-functions\n")
    condition: Condition = {"package": "azure-functions-worker", "file": "requirements.txt"}
    rule = _make_rule("package_forbidden", condition)
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "pass"
    assert "azure-functions-worker" in res.get("detail", "")


def test_package_forbidden_fail(tmp_path: Path) -> None:
    """package_forbidden fails when the forbidden package IS in requirements.txt."""
    req = tmp_path / "requirements.txt"
    req.write_text("azure-functions\nazure-functions-worker==1.0\n")
    condition = cast(
        Condition,
        cast(object, {"package": "azure-functions-worker", "file": "requirements.txt"}),
    )
    rule = _make_rule("package_forbidden", condition)
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "azure-functions-worker" in res.get("detail", "")


def test_package_forbidden_no_requirements_file(tmp_path: Path) -> None:
    """package_forbidden fails when the requirements file is missing."""
    condition_2 = cast(
        Condition,
        cast(object, {"package": "azure-functions-worker", "file": "requirements.txt"}),
    )
    rule = _make_rule("package_forbidden", condition_2)
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "not found" in res.get("detail", "").lower()


def test_package_forbidden_missing_package_field(tmp_path: Path) -> None:
    """package_forbidden fails gracefully when condition is missing the package field."""
    req = tmp_path / "requirements.txt"
    req.write_text("azure-functions\n")
    rule = _make_rule("package_forbidden", {"file": "requirements.txt"})  # no 'package' key
    res = generic_handler(rule, tmp_path)
    assert res["status"] == "fail"
    assert "Missing" in res.get("detail", "")


def test_ast_collection_helpers_handle_syntax_error() -> None:
    broken_source = "def bad(:\n"
    assert _collect_blueprint_aliases(broken_source) == set()
    assert _collect_register_functions_args(broken_source) == set()
    assert _source_contains_blueprint_decorator(broken_source, {"bp"}) == set()


def test_source_contains_blueprint_decorator_returns_empty_for_non_matching_decorator() -> None:
    source = """
bp = Blueprint()

@something_else.route()
def main(req):
    return 'ok'
"""
    assert _source_contains_blueprint_decorator(source, {"bp"}) == set()


def test_create_result_includes_internal_error_flag() -> None:
    res = _create_result("fail", "detail", internal_error=True)
    assert res["internal_error"] == "true"


def test_handle_exception_returns_internal_error_result() -> None:
    result = _handle_exception("unit-test", RuntimeError("boom"))
    assert result["status"] == "fail"
    assert result["internal_error"] == "true"
    assert "Error during unit-test" in result["detail"]


def test_detect_native_dependency_risk_skips_includes_and_flags_and_parses_editable() -> None:
    requirements = """
-r base.txt
--constraint constraints.txt
--index-url https://example.invalid/simple
-e git+https://example.invalid/repo.git#egg=pyodbc
totally@@broken-spec
"""
    matches = _detect_native_dependency_risks(requirements)
    assert [name for name, _ in matches] == ["pyodbc"]


def test_any_of_exists_invalid_host_json_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "host.json").write_text("{ broken", encoding="utf-8")
    rule = _make_rule(
        "any_of_exists", {"targets": ["host.json:.extensions.durableTask", "NOT_SET"]}
    )
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "fail"


def test_file_glob_check_caps_matches_at_five(tmp_path: Path) -> None:
    for i in range(7):
        (tmp_path / f"secret-{i}.txt").write_text("x", encoding="utf-8")

    rule = _make_rule("file_glob_check", {"patterns": ["secret-*.txt"]})
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "fail"
    assert result["detail"].count("secret-") <= 5
