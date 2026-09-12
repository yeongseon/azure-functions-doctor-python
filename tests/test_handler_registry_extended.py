"""Extended tests for the handler registry pattern - covering missing code branches."""

from pathlib import Path
import tempfile
from typing import Any, cast
from unittest.mock import patch

from azure_functions_doctor.handlers import HandlerRegistry, Rule


def test_handler_missing_type_none() -> None:
    """Test handle() with rule type=None (line 197)."""
    registry = HandlerRegistry()
    rule = cast(Rule, {"id": "test_none_type"})
    # type is missing, should be None
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing check type" in result["detail"]


def test_handle_exception_propagation() -> None:
    """Test exceptions caught/handled via _handle_specific_exceptions (line 205-206)."""
    registry = HandlerRegistry()
    # Create a rule that will raise during execution
    rule: Rule = {
        "id": "test_exception_propagation",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": ">=",
            "value": "not_a_version",  # Invalid version string
        },
    }
    result = registry.handle(rule, Path("."))
    # Should fail with internal_error flag set
    assert result["status"] == "fail"
    assert "internal_error" in result


def test_compare_version_invalid_version() -> None:
    """Test _handle_compare_version with InvalidVersion exception (line 243-244)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_invalid_version",
        "type": "compare_version",
        "condition": {
            "target": "func_core_tools",
            "operator": ">=",
            "value": "5.0",
        },
    }
    # Mock func_core_tools to return invalid version
    _target = "azure_functions_doctor.handlers.generic.resolve_target_value"
    with patch(_target, return_value="invalid!!!version"):
        result = registry.handle(rule, Path("."))
        assert result["status"] == "fail"
        assert "unparseable" in result["detail"]


def test_compare_version_unknown_target() -> None:
    """Test _handle_compare_version with unknown target (line 258)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_unknown_target",
        "type": "compare_version",
        "condition": {
            "target": "unknown_thing",
            "operator": ">=",
            "value": "1.0",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Unknown target" in result["detail"]


def test_env_var_exists_missing_target() -> None:
    """Test _handle_env_var_exists with missing target (line 266)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_env_missing_target",
        "type": "env_var_exists",
        "condition": {},  # No target
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing environment variable" in result["detail"]


def test_path_exists_missing_target() -> None:
    """Test _handle_path_exists with missing target (line 280)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_path_missing_target",
        "type": "path_exists",
        "condition": {},  # No target
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing target path" in result["detail"]


def test_path_exists_non_sys_executable_target() -> None:
    """Test _handle_path_exists with non-sys.executable target (line 287)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_path_exists_relative",
            "type": "path_exists",
            "condition": {
                "target": "some_dir",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "missing" in result["detail"]


def test_path_exists_optional() -> None:
    """Test _handle_path_exists with optional flag (line 291)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_path_exists_optional",
            "type": "path_exists",
            "required": False,
            "condition": {
                "target": "nonexistent",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "optional" in result["detail"]


def test_file_exists_missing_target() -> None:
    """Test _handle_file_exists with missing target (line 292)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_file_missing_target",
        "type": "file_exists",
        "condition": {},  # No target
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing file path" in result["detail"]


def test_file_exists_not_found_optional() -> None:
    """Test _handle_file_exists with optional file not found (line 301)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_file_optional_missing",
            "type": "file_exists",
            "required": False,
            "condition": {
                "target": "missing.txt",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "optional" in result["detail"]


def test_package_installed_missing_target() -> None:
    """Test _handle_package_installed with missing target (line 315)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_pkg_missing_target",
        "type": "package_installed",
        "condition": {},  # No target
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing package name" in result["detail"]


def test_source_code_contains_missing_keyword() -> None:
    """Test _handle_source_code_contains with missing keyword (line 329)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_src_missing_keyword",
            "type": "source_code_contains",
            "condition": {},  # No keyword
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Missing or invalid 'keyword'" in result["detail"]


def test_source_code_contains_invalid_keyword_type() -> None:
    """Test _handle_source_code_contains with non-string keyword (line 329)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule = cast(
            Rule,
            {
                "id": "test_src_invalid_keyword_type",
                "type": "source_code_contains",
                "condition": {
                    "keyword": 123,  # Not a string
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Missing or invalid 'keyword'" in result["detail"]


def test_source_code_contains_ast_mode_invalid_keyword() -> None:
    """Test _handle_source_code_contains AST mode with invalid keyword (line 338)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_src_ast_invalid",
            "type": "source_code_contains",
            "condition": {
                "keyword": "   ",  # Only whitespace after strip
                "mode": "ast",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Invalid 'keyword' for AST mode" in result["detail"]


def test_package_declared_missing_package() -> None:
    """Test _handle_package_declared with missing package name (line 364)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule = cast(
            Rule,
            {
                "id": "test_pkg_declared_missing",
                "type": "package_declared",  # Invalid type, cast to bypass mypy
                "condition": {},  # No package
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Missing 'package'" in result["detail"]


def test_package_declared_req_file_not_found() -> None:
    """Test _handle_package_declared with missing requirements file (line 372-373)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule = cast(
            Rule,
            {
                "id": "test_pkg_declared_no_req",
                "type": "package_declared",  # Invalid type, cast to bypass mypy
                "condition": {
                    "package": "requests",
                    "file": "requirements.txt",
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_package_forbidden_req_file_read_exception() -> None:
    """Test _handle_package_forbidden exception during read (line 399-400)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.0.0")

        rule: Rule = {
            "id": "test_pkg_forbidden_read_error",
            "type": "package_forbidden",
            "condition": {
                "package": "azure-functions",
                "file": "requirements.txt",
            },
        }

        # Mock the read_text to raise an exception
        original_path = Path.read_text

        def read_with_error(self: Path, *args: Any, **kwargs: Any) -> str:
            if "requirements.txt" in str(self):
                raise ValueError("Simulated read error")
            return original_path(self, *args, **kwargs)

        with patch.object(Path, "read_text", new=read_with_error):
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"
            assert "internal_error" in result


def test_conditional_exists_durable_detection_exception() -> None:
    """Test _handle_conditional_exists with exception during durable scan (line 429)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create a .py file so the scan loop actually calls _read_project_python_file
        (tmp_path / "durable_func.py").write_text("# placeholder", encoding="utf-8")
        rule: Rule = {
            "id": "test_cond_exists_exc",
            "type": "conditional_exists",
            "condition": {
                "jsonpath": "$.extensions",
            },
        }

        # Patch _read_project_python_file to raise so the except branch is hit

        def read_with_error(path: Path) -> str:
            raise ValueError("Simulated read error")

        with patch(
            "azure_functions_doctor.handlers.generic._read_project_python_file",
            side_effect=read_with_error,
        ):
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"
            assert "internal_error" in result


def test_conditional_exists_missing_jsonpath() -> None:
    """Test _handle_conditional_exists with missing jsonpath (line 444)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create a durable keyword to pass first check
        py_file = tmp_path / "test.py"
        py_file.write_text("import durable_functions")

        rule: Rule = {
            "id": "test_cond_no_jsonpath",
            "type": "conditional_exists",
            "condition": {},  # No jsonpath
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Missing jsonpath" in result["detail"]


def test_conditional_exists_non_string_jsonpath() -> None:
    """Test _handle_conditional_exists with non-string jsonpath (line 450)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create a durable keyword to pass first check
        py_file = tmp_path / "test.py"
        py_file.write_text("import durable_functions")

        rule = cast(
            Rule,
            {
                "id": "test_cond_non_string_jsonpath",
                "type": "conditional_exists",
                "condition": {
                    "jsonpath": 123,  # Not a string
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "must be a string" in result["detail"]


def test_conditional_exists_missing_host_json_durable() -> None:
    """Test _handle_conditional_exists: missing host.json when durable detected (line 458-459)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create durable keyword
        py_file = tmp_path / "test.py"
        py_file.write_text("import durable_functions")

        rule: Rule = {
            "id": "test_cond_missing_host",
            "type": "conditional_exists",
            "condition": {
                "jsonpath": "$.extensions",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "host.json missing" in result["detail"]


def test_any_of_exists_missing_targets() -> None:
    """Test _handle_any_of_exists with missing targets list (line 488)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_any_no_targets",
        "type": "any_of_exists",
        "condition": {},  # No targets
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing 'targets'" in result["detail"]


def test_any_of_exists_host_json_key_traversal() -> None:
    """Test _handle_any_of_exists with host.json key traversal (line 493-494)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensions": {"http": {"enabled": true}}}')

        rule: Rule = {
            "id": "test_any_host_key",
            "type": "any_of_exists",
            "condition": {
                "targets": ["host.json:extensions.http.enabled"],
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "present" in result["detail"]


def test_file_glob_check_missing_patterns() -> None:
    """Test _handle_file_glob_check with missing patterns (line 508)."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_glob_no_patterns",
        "type": "file_glob_check",
        "condition": {},  # No patterns
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing 'patterns'" in result["detail"]


def test_file_glob_check_exception_during_glob() -> None:
    """Test _handle_file_glob_check exception during globbing (line 520)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_glob_exception",
            "type": "file_glob_check",
            "condition": {
                "patterns": ["*.py"],
            },
        }

        # Mock rglob to raise exception
        def rglob_with_error(self: Path, pattern: str) -> list[Path]:
            raise ValueError("Simulated glob error")

        with patch.object(Path, "rglob", new=rglob_with_error):
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"
            assert "internal_error" in result


def test_host_json_property_missing_jsonpath() -> None:
    """Test _handle_host_json_property with missing jsonpath (line 577)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_host_prop_no_path",
            "type": "host_json_property",
            "condition": {},  # No jsonpath
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Missing or invalid 'jsonpath'" in result["detail"]


def test_host_json_property_host_json_not_found() -> None:
    """Test _handle_host_json_property with missing host.json (line 583-584)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_host_prop_missing_file",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.version",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "host.json not found" in result["detail"]


def test_host_json_property_exception_reading() -> None:
    """Test _handle_host_json_property with exception reading host.json."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text("invalid json {")

        rule: Rule = {
            "id": "test_host_prop_bad_json",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.version",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "internal_error" in result


def test_host_json_version_not_json() -> None:
    """Test _handle_host_json_version with invalid JSON (line 556)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text("not valid json {")

        rule: Rule = {
            "id": "test_host_version_invalid_json",
            "type": "host_json_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not valid JSON" in result["detail"]


def test_host_json_version_non_dict() -> None:
    """Test _handle_host_json_version with non-dict JSON (line 566-567)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('["array", "not", "object"]')

        rule: Rule = {
            "id": "test_host_version_non_dict",
            "type": "host_json_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"


def test_host_json_extension_bundle_not_dict() -> None:
    """Test _handle_host_json_extension_bundle_version with non-dict host.json (line 530)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('["not", "object"]')

        rule: Rule = {
            "id": "test_bundle_non_dict",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not a JSON object" in result["detail"]


def test_host_json_extension_bundle_missing() -> None:
    """Test _handle_host_json_extension_bundle_version with missing extensionBundle (line 532)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"version": "2.0"}')

        rule: Rule = {
            "id": "test_bundle_missing",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not configured" in result["detail"]


def test_host_json_extension_bundle_not_dict_value() -> None:
    """Test _handle_host_json_extension_bundle_version with non-dict bundle (line 537-539)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensionBundle": "not_an_object"}')

        rule: Rule = {
            "id": "test_bundle_value_not_dict",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not an object" in result["detail"]


def test_host_json_extension_bundle_wrong_id() -> None:
    """Test _handle_host_json_extension_bundle_version with wrong bundle id."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensionBundle": {"id": "WrongId", "version": "[4.0.0, 5.0.0)"}}')

        rule: Rule = {
            "id": "test_bundle_wrong_id",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not the recommended" in result["detail"]


def test_host_json_extension_bundle_old_version() -> None:
    """Test _handle_host_json_extension_bundle_version with old major version."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        bundle_v3 = (
            '{"extensionBundle": {"id": "Microsoft.Azure.Functions.ExtensionBundle",'
            ' "version": "[3.0.0, 4.0.0)"}}'
        )
        host_file.write_text(bundle_v3)

        rule: Rule = {
            "id": "test_bundle_old_version",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "below" in result["detail"]


def test_host_json_extension_bundle_v4_success() -> None:
    """Test _handle_host_json_extension_bundle_version with v4 range (successful)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        bundle_v4 = (
            '{"extensionBundle": {"id": "Microsoft.Azure.Functions.ExtensionBundle",'
            ' "version": "[4.0.0, 5.0.0)"}}'
        )
        host_file.write_text(bundle_v4)

        rule: Rule = {
            "id": "test_bundle_v4_ok",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "v4" in result["detail"]


def test_local_settings_security_no_file() -> None:
    """Test _handle_local_settings_security when local.settings.json missing."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        rule: Rule = {
            "id": "test_local_settings_missing",
            "type": "local_settings_security",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "skip"
        assert "not present" in result["detail"]


def test_source_code_contains_ast_mode_found() -> None:
    """Test _handle_source_code_contains in AST mode with match found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text(
            """from fastapi import FastAPI
@app.get("/test")
def test():
    pass
"""
        )

        rule: Rule = {
            "id": "test_src_ast_found",
            "type": "source_code_contains",
            "condition": {
                "keyword": "app",
                "mode": "ast",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "found" in result["detail"]


def test_conditional_exists_host_json_exception() -> None:
    """Test _handle_conditional_exists with exception reading host.json (line 458-459)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create durable keyword
        py_file = tmp_path / "test.py"
        py_file.write_text("import durable_functions")
        # Create invalid host.json
        host_file = tmp_path / "host.json"
        host_file.write_text("invalid json {")

        rule: Rule = {
            "id": "test_cond_host_json_exception",
            "type": "conditional_exists",
            "condition": {
                "jsonpath": "$.extensions",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "internal_error" in result


class TestResolveHostJsonPath:
    """Direct coverage for the shared _resolve_host_json_path jsonpath helper."""

    def test_resolves_dotted_path_with_dollar_prefix(self) -> None:
        from azure_functions_doctor.handlers._helpers import _resolve_host_json_path

        data = {"extensions": {"durableTask": {"hubName": "h"}}}
        assert _resolve_host_json_path(data, "$.extensions.durableTask.hubName") == "h"

    def test_resolves_path_without_dollar_prefix(self) -> None:
        from azure_functions_doctor.handlers._helpers import _resolve_host_json_path

        data = {"version": "2.0"}
        assert _resolve_host_json_path(data, "version") == "2.0"

    def test_missing_path_returns_sentinel(self) -> None:
        from azure_functions_doctor.handlers._helpers import (
            _HOST_JSON_MISSING,
            _resolve_host_json_path,
        )

        data: dict[str, object] = {"extensions": {}}
        assert _resolve_host_json_path(data, "$.extensions.missing") is _HOST_JSON_MISSING

    def test_empty_path_returns_root(self) -> None:
        from azure_functions_doctor.handlers._helpers import _resolve_host_json_path

        data = {"a": 1}
        assert _resolve_host_json_path(data, "$.") == data
