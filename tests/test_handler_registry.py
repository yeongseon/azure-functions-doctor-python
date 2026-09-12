"""Tests for the handler registry pattern."""

from pathlib import Path
import sys
import tempfile
from typing import Any, cast
from unittest.mock import patch

from pytest import MonkeyPatch

from azure_functions_doctor.handlers import HandlerRegistry, Rule


def test_handler_registry_initialization() -> None:
    """Test that handler registry initializes with all expected handlers."""
    registry = HandlerRegistry()

    expected_handlers = [
        "compare_version",
        "env_var_exists",
        "path_exists",
        "file_exists",
        "package_installed",
        "source_code_contains",
    ]

    for handler_type in expected_handlers:
        assert handler_type in registry._handlers


def test_handler_registry_unknown_type() -> None:
    """Test registry handling of unknown check types."""
    registry = HandlerRegistry()

    # Create rule with intentionally invalid type for testing error handling
    rule = cast(
        Rule,
        {
            "id": "test_unknown",
            "type": "unknown_type_xyz",
        },
    )

    result = registry.handle(rule, Path("."))

    assert result["status"] == "fail"
    assert "Unknown check type" in result["detail"]


def test_handler_registry_compare_version(tmp_path: Path) -> None:
    """Test version comparison through registry."""
    registry = HandlerRegistry()

    rule: Rule = {
        "id": "test_python_version",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": ">=",
            "value": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    }

    result = registry.handle(rule, tmp_path)

    assert result["status"] == "pass"
    # Detail now clarifies that the local interpreter is the tool runtime.
    detail = result["detail"]
    assert detail.startswith("Python ")
    assert "tool runtime" in detail
    assert f"{rule['condition']['operator']}{rule['condition']['value']}" in detail


def test_handler_registry_env_var_exists() -> None:
    """Test environment variable check through registry."""
    registry = HandlerRegistry()

    rule: Rule = {
        "id": "test_env_var",
        "type": "env_var_exists",
        "condition": {
            "target": "PATH",  # Should exist on all systems
        },
    }

    result = registry.handle(rule, Path("."))

    assert result["status"] == "pass"
    assert "PATH is set" in result["detail"]


def test_handler_registry_path_exists() -> None:
    """Test path existence check through registry."""
    registry = HandlerRegistry()

    rule: Rule = {
        "id": "test_path_exists",
        "type": "path_exists",
        "condition": {
            "target": "sys.executable",
        },
    }

    result = registry.handle(rule, Path("."))

    assert result["status"] == "pass"
    assert "exists" in result["detail"]


def test_handler_registry_file_exists() -> None:
    """Test file existence check through registry."""
    registry = HandlerRegistry()

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test content")
        tmp_path = Path(tmp.name)

    try:
        rule: Rule = {
            "id": "test_file_exists",
            "type": "file_exists",
            "condition": {
                "target": tmp_path.name,
            },
        }

        result = registry.handle(rule, tmp_path.parent)

        assert result["status"] == "pass"
        assert "exists" in result["detail"]

    finally:
        tmp_path.unlink()


def test_handler_registry_package_installed() -> None:
    """Test package installation check through registry."""
    registry = HandlerRegistry()

    # Test with a standard library module that should always exist
    rule: Rule = {
        "id": "test_package_installed",
        "type": "package_installed",
        "condition": {
            "target": "os",
        },
    }

    result = registry.handle(rule, Path("."))

    assert result["status"] == "pass"
    assert "is installed" in result["detail"]


def test_handler_registry_source_code_contains() -> None:
    """Test source code search through registry."""
    registry = HandlerRegistry()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create a Python file with specific content
        py_file = tmp_path / "test_file.py"
        py_file.write_text("# Test keyword found here")

        rule: Rule = {
            "id": "test_source_code_contains",
            "type": "source_code_contains",
            "condition": {
                "keyword": "Test keyword",
            },
        }

        result = registry.handle(rule, tmp_path)

        assert result["status"] == "pass"
        assert "found" in result["detail"]


def test_handler_registry_exception_handling() -> None:
    """Test registry exception handling."""
    registry = HandlerRegistry()

    # Create a rule that will cause an exception (missing condition)
    rule: Rule = {
        "id": "test_exception",
        "type": "compare_version",
        "condition": {},  # Missing required fields
    }

    result = registry.handle(rule, Path("."))

    # Should handle the exception gracefully
    assert result["status"] == "fail"
    assert "Missing condition fields" in result["detail"]


def test_handler_registry_optional_rules() -> None:
    """Test registry handling of optional rules."""
    registry = HandlerRegistry()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        rule: Rule = {
            "id": "test_optional_file",
            "type": "file_exists",
            "required": False,
            "condition": {
                "target": "nonexistent_file.txt",
            },
        }

        result = registry.handle(rule, tmp_path)

    # Optional marking now happens during aggregation, so handlers still return fail here.
    assert result["status"] == "fail"
    assert "optional" in result["detail"]


"""Extended tests for the handler registry pattern - covering missing code branches."""


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
        # Create a durable keyword to pass first check
        py_file = tmp_path / "test.py"
        py_file.write_text("import durable_functions")

        rule: Rule = {
            "id": "test_cond_exists_exc",
            "type": "conditional_exists",
            "condition": {
                "jsonpath": "$.extensions",
            },
        }

        # Mock _read_project_python_file to raise exception

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


def _bundle_host(version: str) -> str:
    return (
        '{"extensionBundle": {"id": "Microsoft.Azure.Functions.ExtensionBundle",'
        f' "version": "{version}"}}}}'
    )


def test_extension_bundle_v4_wildcard_passes() -> None:
    """[4.*, 5.0.0) is a documented v4 range and should pass."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "host.json").write_text(_bundle_host("[4.*, 5.0.0)"))
        rule: Rule = {"type": "host_json_extension_bundle_version", "condition": {}}
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"


def test_extension_bundle_overbroad_upper_fails() -> None:
    """[4.0.0, 6.0.0) is over-broad (wrong upper bound) and must fail."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "host.json").write_text(_bundle_host("[4.0.0, 6.0.0)"))
        rule: Rule = {"type": "host_json_extension_bundle_version", "condition": {}}
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "does not match" in result["detail"]


def test_extension_bundle_nonzero_upper_minor_fails() -> None:
    """[4.0.0, 5.1.0) widens past the exclusive 5.0.0 bound and must fail."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "host.json").write_text(_bundle_host("[4.0.0, 5.1.0)"))
        rule: Rule = {"type": "host_json_extension_bundle_version", "condition": {}}
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "does not match" in result["detail"]


def test_extension_bundle_inclusive_upper_fails() -> None:
    """[4.0.0, 5.0.0] with an inclusive upper bound must fail."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "host.json").write_text(_bundle_host("[4.0.0, 5.0.0]"))
        rule: Rule = {"type": "host_json_extension_bundle_version", "condition": {}}
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"


def test_extension_bundle_malformed_range_fails() -> None:
    """A non-range version string must fail as invalid."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "host.json").write_text(_bundle_host("4.0.0"))
        rule: Rule = {"type": "host_json_extension_bundle_version", "condition": {}}
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not a valid range" in result["detail"]


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


def test_package_forbidden_read_exception() -> None:
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


def test_source_code_contains_not_found() -> None:
    """Test _handle_source_code_contains with keyword not found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")

        rule: Rule = {
            "id": "test_src_not_found",
            "type": "source_code_contains",
            "condition": {
                "keyword": "NonexistentKeyword",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_source_code_contains_ast_not_found() -> None:
    """Test _handle_source_code_contains AST mode with no match."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text(
            """def test():
    pass
"""
        )

        rule: Rule = {
            "id": "test_src_ast_not_found",
            "type": "source_code_contains",
            "condition": {
                "keyword": "@app.route",
                "mode": "ast",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_compare_version_func_core_tools_not_installed() -> None:
    """Test _handle_compare_version with func not installed."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_func_not_installed",
        "type": "compare_version",
        "condition": {
            "target": "func_core_tools",
            "operator": ">=",
            "value": "4.0",
        },
    }
    _target = "azure_functions_doctor.handlers.generic.resolve_target_value"
    with patch(_target, return_value="not_installed"):
        result = registry.handle(rule, Path("."))
        assert result["status"] == "fail"
        assert "func:" in result["detail"]


def test_package_declared_success() -> None:
    """Test _handle_package_declared with package found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0\ndjango==4.1.0")

        rule = cast(
            Rule,
            {
                "id": "test_pkg_declared_found",
                "type": "package_declared",  # Invalid type, cast to bypass mypy
                "condition": {
                    "package": "requests",
                    "file": "requirements.txt",
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "declared" in result["detail"]


def test_package_declared_not_found() -> None:
    """Test _handle_package_declared with package not found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("django==4.1.0")

        rule = cast(
            Rule,
            {
                "id": "test_pkg_declared_not_found",
                "type": "package_declared",  # Invalid type, cast to bypass mypy
                "condition": {
                    "package": "requests",
                    "file": "requirements.txt",
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not declared" in result["detail"]


def test_package_forbidden_success() -> None:
    """Test _handle_package_forbidden with package not found (safe)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        rule: Rule = {
            "id": "test_pkg_forbidden_safe",
            "type": "package_forbidden",
            "condition": {
                "package": "azure-functions",
                "file": "requirements.txt",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "not declared" in result["detail"]


def test_package_forbidden_found() -> None:
    """Test _handle_package_forbidden with forbidden package found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("azure-functions==1.0.0")

        rule: Rule = {
            "id": "test_pkg_forbidden_found",
            "type": "package_forbidden",
            "condition": {
                "package": "azure-functions",
                "file": "requirements.txt",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "should not be declared" in result["detail"]


def test_executable_exists_found() -> None:
    """Test _handle_executable_exists when executable is found."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_executable_found",
        "type": "executable_exists",
        "condition": {
            "target": "python",  # Python should be in PATH
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "detected" in result["detail"]


def test_executable_exists_not_found() -> None:
    """Test _handle_executable_exists when executable is not found."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_executable_not_found",
        "type": "executable_exists",
        "condition": {
            "target": "nonexistent_executable_12345",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "not found" in result["detail"]


def test_executable_exists_missing_target() -> None:
    """Test _handle_executable_exists with missing target."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_executable_missing_target",
        "type": "executable_exists",
        "condition": {},
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing 'target'" in result["detail"]


def test_executable_exists_python3_fallback(monkeypatch: MonkeyPatch) -> None:
    """Test python target falls back to python3 when python is not on PATH."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python3_fallback",
        "type": "executable_exists",
        "condition": {
            "target": "python",
        },
    }

    # Simulate: 'python' not found, 'python3' found
    def fake_which(name: str) -> str | None:
        return "/usr/bin/python3" if name == "python3" else None

    monkeypatch.setattr("shutil.which", fake_which)
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "python detected" in result["detail"]


def test_executable_exists_python_no_fallback_needed(monkeypatch: MonkeyPatch) -> None:
    """Test python target found directly — no fallback triggered."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_direct",
        "type": "executable_exists",
        "condition": {
            "target": "python",
        },
    }

    def fake_which(name: str) -> str | None:
        return "/usr/bin/python" if name == "python" else None

    monkeypatch.setattr("shutil.which", fake_which)
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "python detected" in result["detail"]


def test_executable_exists_python_neither_found(monkeypatch: MonkeyPatch) -> None:
    """Test python target fails when neither python nor python3 on PATH."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_neither",
        "type": "executable_exists",
        "condition": {
            "target": "python",
        },
    }

    monkeypatch.setattr("shutil.which", lambda name: None)
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "not found" in result["detail"]


def test_executable_exists_non_python_no_fallback(monkeypatch: MonkeyPatch) -> None:
    """Test non-python target does NOT trigger python3 fallback."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_non_python_no_fallback",
        "type": "executable_exists",
        "condition": {
            "target": "func",
        },
    }

    # python3 exists but should NOT be tried for 'func'
    def fake_which(name: str) -> str | None:
        return "/usr/bin/python3" if name == "python3" else None

    monkeypatch.setattr("shutil.which", fake_which)
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "not found" in result["detail"]


def test_executable_exists_python3_tries_python(monkeypatch: MonkeyPatch) -> None:
    """Test python3 target falls back to python when python3 is not on PATH."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python3_tries_python",
        "type": "executable_exists",
        "condition": {
            "target": "python3",
        },
    }

    # Simulate: 'python3' not found, 'python' found
    def fake_which(name: str) -> str | None:
        return "/usr/bin/python" if name == "python" else None

    monkeypatch.setattr("shutil.which", fake_which)
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "python3 detected" in result["detail"]


def test_executable_exists_python_tries_py_on_windows(monkeypatch: MonkeyPatch) -> None:
    """Test python target falls back to py on Windows when python/python3 not found."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_tries_py_windows",
        "type": "executable_exists",
        "condition": {
            "target": "python",
        },
    }

    # Simulate Windows platform and 'py' available
    def fake_which(name: str) -> str | None:
        return "C:\\Python\\py.exe" if name == "py" else None

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("shutil.which", fake_which)
    # Force reimport/re-evaluation by reloading the module or accessing the dict directly
    # Note: Since _PYTHON_CANDIDATES is evaluated at module load time, we need to patch it directly
    from azure_functions_doctor.handlers import _PYTHON_CANDIDATES

    monkeypatch.setitem(_PYTHON_CANDIDATES, "python", ["python", "python3", "py"])

    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "python detected" in result["detail"]


def test_executable_exists_python3_tries_py_on_windows(monkeypatch: MonkeyPatch) -> None:
    """Test python3 target falls back to py on Windows when python3/python not found."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python3_tries_py_windows",
        "type": "executable_exists",
        "condition": {
            "target": "python3",
        },
    }

    # Simulate Windows platform and only 'py' available
    def fake_which(name: str) -> str | None:
        return "C:\\Python\\py.exe" if name == "py" else None

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("shutil.which", fake_which)
    from azure_functions_doctor.handlers import _PYTHON_CANDIDATES

    monkeypatch.setitem(_PYTHON_CANDIDATES, "python3", ["python3", "python", "py"])

    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "python3 detected" in result["detail"]


def test_executable_exists_unknown_target_no_fallback(monkeypatch: MonkeyPatch) -> None:
    """Test unknown target (e.g., node) only tries itself, no fallback."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_node_no_fallback",
        "type": "executable_exists",
        "condition": {
            "target": "node",
        },
    }

    call_count = {"count": 0}
    tried_names = []

    def fake_which(name: str) -> str | None:
        call_count["count"] += 1
        tried_names.append(name)
        return None

    monkeypatch.setattr("shutil.which", fake_which)
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "node not found" in result["detail"]
    # Verify that only 'node' was tried, no fallback
    assert tried_names == ["node"]


def test_callable_detection_found() -> None:
    """Test _handle_callable_detection with pattern found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "main.py"
        py_file.write_text(
            """import azure.functions as func
from fastapi import FastAPI
fastapi_app = FastAPI()
app = func.AsgiFunctionApp(app=fastapi_app)
"""
        )

        rule: Rule = {
            "id": "test_callable_found",
            "type": "callable_detection",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "Detected" in result["detail"]


def test_callable_detection_not_found() -> None:
    """Test _handle_callable_detection with no patterns found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "main.py"
        py_file.write_text("def hello():\n    return 'world'")

        rule: Rule = {
            "id": "test_callable_not_found",
            "type": "callable_detection",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "skip"
        assert "No ASGI/WSGI" in result["detail"]


def test_any_of_exists_env_var() -> None:
    """Test _handle_any_of_exists with env var match."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_any_env_var",
        "type": "any_of_exists",
        "condition": {
            "targets": ["PATH"],  # PATH should exist
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"
    assert "set" in result["detail"]


def test_any_of_exists_file_path() -> None:
    """Test _handle_any_of_exists with file path match."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        rule: Rule = {
            "id": "test_any_file_path",
            "type": "any_of_exists",
            "condition": {
                "targets": ["test.txt"],
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "present" in result["detail"]


def test_file_glob_check_found() -> None:
    """Test _handle_file_glob_check with unwanted files found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("compiled")

        rule: Rule = {
            "id": "test_glob_found",
            "type": "file_glob_check",
            "condition": {
                "patterns": ["*.pyc"],
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Found unwanted files" in result["detail"]


def test_file_glob_check_not_found() -> None:
    """Test _handle_file_glob_check with no unwanted files."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rule: Rule = {
            "id": "test_glob_not_found",
            "type": "file_glob_check",
            "condition": {
                "patterns": ["*.pyc"],
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "No unwanted files" in result["detail"]


def test_host_json_version_correct() -> None:
    """Test _handle_host_json_version with correct version."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"version": "2.0"}')

        rule: Rule = {
            "id": "test_host_version_correct",
            "type": "host_json_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert '"2.0"' in result["detail"]


def test_host_json_version_wrong() -> None:
    """Test _handle_host_json_version with wrong version."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"version": "1.0"}')

        rule: Rule = {
            "id": "test_host_version_wrong",
            "type": "host_json_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "expected" in result["detail"]


def test_host_json_extension_bundle_v5_success() -> None:
    """Test _handle_host_json_extension_bundle_version with v5 range (newer than v4)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        bundle_v5 = (
            '{"extensionBundle": {"id": "Microsoft.Azure.Functions.ExtensionBundle",'
            ' "version": "[5.0.0, 6.0.0)"}}'
        )
        host_file.write_text(bundle_v5)

        rule: Rule = {
            "id": "test_bundle_v5_ok",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "does not match" in result["detail"]


def test_conditional_exists_no_durable_detected() -> None:
    """Test _handle_conditional_exists when no durable functions detected."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text("print('regular python code')")

        rule: Rule = {
            "id": "test_cond_no_durable",
            "type": "conditional_exists",
            "condition": {
                "jsonpath": "$.extensions",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "skip"
        assert "No Durable Functions" in result["detail"]


def test_host_json_property_found() -> None:
    """Test _handle_host_json_property with property found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"version": "2.0", "extensions": {"http": {"enabled": true}}}')

        rule: Rule = {
            "id": "test_host_prop_found",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.extensions.http.enabled",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "contains" in result["detail"]


def test_host_json_property_not_found() -> None:
    """Test _handle_host_json_property with property not found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"version": "2.0"}')

        rule: Rule = {
            "id": "test_host_prop_not_found",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.extensions.http.enabled",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_env_var_not_exists() -> None:
    """Test _handle_env_var_exists with env var not set."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_env_not_exists",
        "type": "env_var_exists",
        "condition": {
            "target": "NONEXISTENT_ENV_VAR_XYZ123",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "not set" in result["detail"]


def test_path_exists_valid() -> None:
    """Test _handle_path_exists with existing path."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        rule: Rule = {
            "id": "test_path_exists_valid",
            "type": "path_exists",
            "condition": {
                "target": "subdir",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "exists" in result["detail"]


def test_file_exists_valid() -> None:
    """Test _handle_file_exists with existing file."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        rule: Rule = {
            "id": "test_file_exists_valid",
            "type": "file_exists",
            "condition": {
                "target": "test.txt",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "exists" in result["detail"]


def test_source_code_contains_with_syntax_error() -> None:
    """Test _handle_source_code_contains with syntax error in Python file."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        # Create a file with syntax error
        py_file.write_text("def broken(\n  # intentional syntax error")

        rule: Rule = {
            "id": "test_src_syntax_error",
            "type": "source_code_contains",
            "condition": {
                "keyword": "@app.route",
                "mode": "ast",
            },
        }
        result = registry.handle(rule, tmp_path)
        # When AST parsing fails, should return no match found
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_file_exists_excluded_dir() -> None:
    """Test that __pycache__ directories are skipped."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create __pycache__ directory with a Python file
        pycache_dir = tmp_path / "__pycache__"
        pycache_dir.mkdir()
        pycache_file = pycache_dir / "test.py"
        pycache_file.write_text("excluded_keyword")

        rule: Rule = {
            "id": "test_excluded_pycache",
            "type": "source_code_contains",
            "condition": {
                "keyword": "excluded_keyword",
            },
        }
        result = registry.handle(rule, tmp_path)
        # File in __pycache__ should be skipped, so not found
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_compare_version_python_fail() -> None:
    """Test _handle_compare_version with Python version check that fails."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_version_fail",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": "<",
            "value": "1.0",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"


def test_compare_version_python_equal(tmp_path: Path) -> None:
    """Test _handle_compare_version with Python version == operator."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_version_eq",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": "==",
            "value": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
    }
    result = registry.handle(rule, tmp_path)
    assert result["status"] == "pass"


def test_compare_version_python_greater() -> None:
    """Test _handle_compare_version with Python > operator."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_version_gt",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": ">",
            "value": "1.0",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"


def test_compare_version_python_less() -> None:
    """Test _handle_compare_version with Python < operator."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_version_lt",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": "<",
            "value": "99.0",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"


def test_compare_version_python_less_equal() -> None:
    """Test _handle_compare_version with Python <= operator."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_python_version_le",
        "type": "compare_version",
        "condition": {
            "target": "python",
            "operator": "<=",
            "value": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
    }
    result = registry.handle(rule, Path("."))
    assert result["status"] == "pass"


def test_compare_version_func_tools_success() -> None:
    """Test _handle_compare_version with func_core_tools that has valid version."""
    registry = HandlerRegistry()
    rule: Rule = {
        "id": "test_func_tools_success",
        "type": "compare_version",
        "condition": {
            "target": "func_core_tools",
            "operator": ">=",
            "value": "1.0",
        },
    }
    with patch(
        "azure_functions_doctor.handlers.generic.resolve_target_value", return_value="5.0.0"
    ):
        result = registry.handle(rule, Path("."))
        assert result["status"] == "pass"


def test_host_json_version_exception_reading() -> None:
    """Test _handle_host_json_version with exception reading host.json."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text("not json {")

        rule: Rule = {
            "id": "test_host_version_exception",
            "type": "host_json_version",
            "condition": {},
        }

        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not valid JSON" in result["detail"]


def test_any_of_exists_no_targets_not_list() -> None:
    """Test _handle_any_of_exists with targets that is not a list."""
    registry = HandlerRegistry()
    rule = cast(
        Rule,
        {
            "id": "test_any_targets_not_list",
            "type": "any_of_exists",
            "condition": {
                "targets": "not_a_list",
            },
        },
    )
    result = registry.handle(rule, Path("."))
    assert result["status"] == "fail"
    assert "Missing 'targets'" in result["detail"]


def test_package_declared_with_comments() -> None:
    """Test _handle_package_declared skips commented lines in requirements file."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("# requests==1.0.0\ndjango==4.1.0\n# another comment")

        rule = cast(
            Rule,
            {
                "id": "test_pkg_declared_with_comments",
                "type": "package_declared",  # Invalid type, cast to bypass mypy
                "condition": {
                    "package": "requests",
                    "file": "requirements.txt",
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        # Comments should be skipped, so requests not found
        assert result["status"] == "fail"


def test_package_declared_case_insensitive() -> None:
    """Test _handle_package_declared is case-insensitive."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("Requests==2.28.0")

        rule = cast(
            Rule,
            {
                "id": "test_pkg_declared_case",
                "type": "package_declared",  # Invalid type, cast to bypass mypy
                "condition": {
                    "package": "requests",
                    "file": "requirements.txt",
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        # Should match despite case difference
        assert result["status"] == "pass"


def test_host_json_extension_bundle_missing_id() -> None:
    """Test _handle_host_json_extension_bundle_version with missing id field."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensionBundle": {"version": "[4.0.0, 5.0.0)"}}')

        rule: Rule = {
            "id": "test_bundle_missing_id",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not the recommended" in result["detail"]


# Tests for uncovered exception branches and edge cases


def test_read_python_file_permission_error() -> None:
    """Test _read_project_python_file with PermissionError in source_code_contains handler."""
    from unittest.mock import patch

    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text("import requests")

        # Mock Path.read_text to raise PermissionError on first call
        original_read_text = Path.read_text
        call_count = [0]

        def mock_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            call_count[0] += 1
            if call_count[0] == 1 and "test.py" in str(self):
                raise PermissionError("Access denied")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", mock_read_text):
            rule: Rule = {
                "id": "test_permission_error",
                "type": "source_code_contains",
                "condition": {
                    "file": "test.py",
                    "keyword": "import",
                },
            }
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"
            assert "not found" in result["detail"]


def test_read_python_file_unicode_decode_then_oserror() -> None:
    """Test _read_project_python_file with UnicodeDecodeError falling back to OSError."""
    from unittest.mock import patch

    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text("import requests")

        # Mock to raise UnicodeDecodeError, then OSError on retry
        original_read_text = Path.read_text
        call_count = [0]

        def mock_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            call_count[0] += 1
            if "test.py" in str(self):
                if call_count[0] == 1:
                    raise UnicodeDecodeError("utf-8", b"", 0, 1, "invalid start byte")
                elif call_count[0] == 2:
                    raise OSError("I/O error")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", mock_read_text):
            rule: Rule = {
                "id": "test_unicode_then_oserror",
                "type": "source_code_contains",
                "condition": {
                    "file": "test.py",
                    "keyword": "import",
                },
            }
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"


def test_read_python_file_memory_error() -> None:
    """Test _read_project_python_file with MemoryError branch."""
    from unittest.mock import patch

    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        py_file = tmp_path / "test.py"
        py_file.write_text("import requests")

        # Mock to raise MemoryError
        original_read_text = Path.read_text

        def mock_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if "test.py" in str(self):
                raise MemoryError("Out of memory")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", mock_read_text):
            rule: Rule = {
                "id": "test_memory_error",
                "type": "source_code_contains",
                "condition": {
                    "file": "test.py",
                    "keyword": "import",
                },
            }
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"


def test_conditional_exists_missing_jsonpath_durable() -> None:
    """Test _handle_conditional_exists when durable detected but jsonpath missing."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create a Python file with durable keyword to trigger durable detection
        py_file = tmp_path / "durable_test.py"
        py_file.write_text("from durable_functions import orchestrator")

        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensions": {"durableTask": {}}}')

        rule: Rule = {
            "id": "test_conditional_no_jsonpath",
            "type": "conditional_exists",
            "condition": {
                "keyword": "durable",
                # jsonpath missing
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "jsonpath" in result["detail"].lower()


def test_any_of_exists_no_targets_provided() -> None:
    """Test _handle_any_of_exists with empty targets list."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        rule: Rule = {
            "id": "test_any_of_empty",
            "type": "any_of_exists",
            "condition": {
                "targets": [],  # Empty targets
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"


def test_file_glob_no_patterns() -> None:
    """Test _handle_file_glob_check with no patterns provided."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        rule: Rule = {
            "id": "test_glob_no_patterns",
            "type": "file_glob_check",
            "condition": {
                "patterns": [],  # Empty patterns
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"


def test_host_json_version_invalid_json() -> None:
    """Test _handle_host_json_version with invalid JSON."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text("not valid json{")

        rule: Rule = {
            "id": "test_host_json_invalid",
            "type": "host_json_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"


def test_host_json_property_invalid_jsonpath_type() -> None:
    """Test _handle_host_json_property with non-string jsonpath."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"key": "value"}')

        rule = cast(
            Rule,
            {
                "id": "test_host_prop_bad_jsonpath",
                "type": "host_json_property",
                "condition": {
                    "jsonpath": 123,  # Pass int to test type validation
                },
            },
        )
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "invalid" in result["detail"].lower()


def test_extension_bundle_id_mismatch() -> None:
    """Test _handle_host_json_extension_bundle_version with mismatched id."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        bundle_custom = (
            '{"extensionBundle": {"id": "Microsoft.Azure.Functions.ExtensionBundle.Custom",'
            ' "version": "[4.0.0, 5.0.0)"}}'
        )
        host_file.write_text(bundle_custom)

        rule: Rule = {
            "id": "test_bundle_wrong_id",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not the recommended" in result["detail"]


def test_extension_bundle_version_old() -> None:
    """Test extension bundle with old version string."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        bundle_315 = (
            '{"extensionBundle": {"id": "Microsoft.Azure.Functions.ExtensionBundle",'
            ' "version": "[3.15.0, 4.0.0)"}}'
        )
        host_file.write_text(bundle_315)

        rule: Rule = {
            "id": "test_bundle_old_version",
            "type": "host_json_extension_bundle_version",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "below" in result["detail"].lower() or "upgrade" in result["detail"].lower()


# Tests for additional uncovered branches


def test_path_exists_empty_sys_executable() -> None:
    """Test _handle_path_exists with sys.executable being empty."""
    import sys as sys_module

    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Temporarily mock sys.executable to be empty
        original_executable = sys_module.executable
        try:
            sys_module.executable = ""
            rule: Rule = {
                "id": "test_empty_executable",
                "type": "path_exists",
                "condition": {
                    "target": "sys.executable",
                },
            }
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"
            assert "empty" in result["detail"].lower()
        finally:
            sys_module.executable = original_executable


def test_conditional_exists_durable_with_all_keywords() -> None:
    """Test _handle_conditional_exists durable detection with all keywords."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create Python files with different durable keywords
        (tmp_path / "orchest.py").write_text("def orchestrator():")
        (tmp_path / "host.json").write_text('{"extensions": {"durableTask": {}}}')

        rule: Rule = {
            "id": "test_durable_orchestrator",
            "type": "conditional_exists",
            "condition": {
                "keyword": "durable",
                "jsonpath": "$.extensions.durableTask",
            },
        }
        result = registry.handle(rule, tmp_path)
        # Should find durable usage and pass the jsonpath check
        assert result["status"] == "pass"


def test_conditional_exists_durable_context() -> None:
    """Test _handle_conditional_exists with DurableOrchestrationContext detection."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        (tmp_path / "ctx.py").write_text("context: DurableOrchestrationContext")
        (tmp_path / "host.json").write_text('{"version": "2.0"}')

        rule: Rule = {
            "id": "test_durable_context",
            "type": "conditional_exists",
            "condition": {
                "keyword": "durable",
                "jsonpath": "$.version",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"
        assert "version" in result["detail"]


def test_host_json_property_jsonpath_with_dollars() -> None:
    """Test _handle_host_json_property with jsonpath using $ notation."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"version": "2.0", "functionTimeout": "00:10:00"}')

        rule: Rule = {
            "id": "test_jsonpath_dollar",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.functionTimeout",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"


def test_host_json_property_nested_jsonpath() -> None:
    """Test _handle_host_json_property with nested jsonpath."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensions": {"durableTask": {"tracing": {"enabled": true}}}}')

        rule: Rule = {
            "id": "test_nested_jsonpath",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.extensions.durableTask.tracing.enabled",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "pass"


def test_host_json_property_nested_jsonpath_not_found() -> None:
    """Test _handle_host_json_property with nested jsonpath not found."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        host_file = tmp_path / "host.json"
        host_file.write_text('{"extensions": {"durableTask": {}}}')

        rule: Rule = {
            "id": "test_nested_not_found",
            "type": "host_json_property",
            "condition": {
                "jsonpath": "$.extensions.durableTask.tracing.enabled",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]


def test_callable_detection_finds_fastapi() -> None:
    """Test _handle_callable_detection finds FastAPI pattern."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")

        rule: Rule = {
            "id": "test_callable_fastapi",
            "type": "callable_detection",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"  # framework present but callable not exposed


def test_local_settings_json_exists() -> None:
    """Test _handle_local_settings_json_security when file exists."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "local.settings.json").write_text('{"Values": {}}')

        rule: Rule = {
            "id": "test_local_settings_exists",
            "type": "local_settings_security",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] in ("pass", "fail")  # pass if not git-tracked or git unavailable


def test_callable_detection_skip_without_framework() -> None:
    """callable_detection returns skip when no framework signal is present."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "main.py").write_text("def my_func(): return 42")

        rule: Rule = {
            "id": "test_no_callable",
            "type": "callable_detection",
            "condition": {},
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "skip"  # No framework => plain FunctionApp, skip


# Tests for exception branches in package handlers


def test_package_declared_read_exception() -> None:
    """Test _handle_package_declared with file read exception (line 372-373)."""
    from unittest.mock import patch

    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create the requirements file so it exists
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        # Mock read_text to raise an exception after the file exists check
        original_read_text = Path.read_text

        def mock_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if "requirements.txt" in str(self):
                raise PermissionError("Cannot read file")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", mock_read_text):
            rule = cast(
                Rule,
                {
                    "id": "test_pkg_declared_read_error",
                    "type": "package_declared",  # Invalid type, cast to bypass mypy
                    "condition": {
                        "package": "requests",
                        "file": "requirements.txt",
                    },
                },
            )
            result = registry.handle(rule, tmp_path)
            assert result["status"] == "fail"
            # Should trigger _handle_specific_exceptions
            assert "internal_error" in result or "error" in result["detail"].lower()


def test_package_forbidden_missing_package() -> None:
    """Test _handle_package_forbidden with missing package (line 391)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.28.0")

        rule: Rule = {
            "id": "test_pkg_forbidden_missing",
            "type": "package_forbidden",
            "condition": {},  # No package
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "Missing 'package'" in result["detail"]


def test_package_forbidden_file_not_found() -> None:
    """Test _handle_package_forbidden with missing requirements file (line 396)."""
    registry = HandlerRegistry()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Don't create requirements.txt

        rule: Rule = {
            "id": "test_pkg_forbidden_no_req",
            "type": "package_forbidden",
            "condition": {
                "package": "azure-functions",
                "file": "requirements.txt",
            },
        }
        result = registry.handle(rule, tmp_path)
        assert result["status"] == "fail"
        assert "not found" in result["detail"]
