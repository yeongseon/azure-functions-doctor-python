"""Tests for v2 programming model detection functionality."""

from pathlib import Path
import tempfile
from unittest.mock import patch

from azure_functions_doctor.doctor import Doctor

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
UNSUPPORTED_V1_VALUE = (
    "Detected legacy function.json files. azure-functions-doctor supports the Python v2 "
    "decorator model only."
)
UNSUPPORTED_V1_HINT = (
    "Migrate to the Python v2 programming model (function_app.py + func.FunctionApp() "
    "with decorators), or skip azure-functions-doctor for this repository."
)
UNKNOWN_VALUE = "No function_app.py, FunctionApp()/Blueprint() usage, or trigger decorators found."
UNKNOWN_HINT = (
    "Expected: function_app.py with func.FunctionApp() and trigger decorators "
    "(@app.route, @app.timer_trigger, etc.). This tool supports v2 projects only."
)


class TestProgrammingModelDetection:
    """Test v2-only programming model detection logic."""

    def test_detect_v2_with_decorators(self) -> None:
        """Test v2 detection when @app decorators are present."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_file = temp_path / "function_app.py"
            python_file.write_text("""
import azure.functions as func

app = func.FunctionApp()

@app.route(route="test", auth_level=func.AuthLevel.Anonymous)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello")
""")

            doctor = Doctor(str(temp_path))
            assert doctor.programming_model == "v2"

    def test_detect_unknown_when_no_signals(self) -> None:
        """Test unknown detection when no v1 or v2 signals are found."""
        doctor = Doctor(str(FIXTURES_DIR / "unknown"))
        assert doctor.programming_model == "unknown"

    def test_detect_unsupported_v1_when_only_function_json(self) -> None:
        """Test v1-only projects are reported as unsupported."""
        doctor = Doctor(str(FIXTURES_DIR / "v1"))
        assert doctor.programming_model == "unsupported_v1"

    def test_detect_mixed_when_both_present(self) -> None:
        """Test mixed v1/v2 projects are detected explicitly."""
        doctor = Doctor(str(FIXTURES_DIR / "mixed"))
        assert doctor.programming_model == "mixed"

    def test_detect_v2_with_functionapp_without_decorators(self) -> None:
        """Test a scaffolded FunctionApp without decorators still counts as v2."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_file = temp_path / "function_app.py"
            python_file.write_text("""
import azure.functions as func

app = func.FunctionApp()
""")

            doctor = Doctor(str(temp_path))
            assert doctor.programming_model == "v2"

    def test_has_v2_decorators_with_various_patterns(self) -> None:
        """Test _has_v2_decorators with various @app patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_cases = [
                "@app.route(route='test')",
                "@app.schedule(schedule='0 */5 * * * *')",
                "@app.timer_trigger(schedule='0 */5 * * * *')",
                "@app.blob_trigger(arg_name='myblob', path='samples-workitems/{name}')",
                (
                    "@app.cosmos_db_trigger("
                    "arg_name='documents', database_name='ToDoList', "
                    "collection_name='Items')"
                ),
            ]

            for i, pattern in enumerate(test_cases):
                python_file = temp_path / f"test_{i}.py"
                python_file.write_text(f"""
import azure.functions as func

app = func.FunctionApp()

{pattern}
def test_function():
    pass
""")

                doctor = Doctor(str(temp_path))
                assert doctor.programming_model == "v2"

    def test_has_v2_decorators_ignores_comments(self) -> None:
        """Test that @app in comments does not count as a decorator."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_file = temp_path / "main.py"
            python_file.write_text("""
# This is a comment with @app.route but it should not count
print('Hello World')

def some_function():
    # Another comment with @app.schedule
    pass
""")

            doctor = Doctor(str(temp_path))
            assert doctor.programming_model == "unknown"

    def test_has_v2_decorators_handles_file_read_errors(self) -> None:
        """Test that file read errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_file = temp_path / "function_app.py"
            python_file.write_text("""
import azure.functions as func

app = func.FunctionApp()

@app.route(route="test", auth_level=func.AuthLevel.Anonymous)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello")
""")

            with patch("pathlib.Path.read_text", side_effect=OSError("Permission denied")):
                doctor = Doctor(str(temp_path))
                assert doctor.programming_model == "unknown"

    def test_detect_v2_with_nested_decorators(self) -> None:
        """Test v2 detection with @app decorators in subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            nested_dir = temp_path / "functions"
            nested_dir.mkdir()

            python_file = nested_dir / "function_app.py"
            python_file.write_text("""
import azure.functions as func

app = func.FunctionApp()

@app.route(route="test", auth_level=func.AuthLevel.Anonymous)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello")
""")

            doctor = Doctor(str(temp_path))
            assert doctor.programming_model == "v2"

    def test_has_v2_decorators_custom_variable_name(self) -> None:
        """Test AST detection works with a non-'app' FunctionApp variable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_file = temp_path / "function_app.py"
            python_file.write_text("""
import azure.functions as func

fa = func.FunctionApp()

@fa.route(route="test", auth_level=func.AuthLevel.Anonymous)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello")
""")
            doctor = Doctor(str(temp_path))
            assert doctor.programming_model == "v2"
            assert doctor._has_v2_decorators() is True

    def test_has_v2_decorators_comment_not_counted_ast(self) -> None:
        """Test that @app. in a comment is not detected by AST mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            python_file = temp_path / "main.py"
            python_file.write_text("""
# @app.route() -- not a real decorator
x = 1
""")
            doctor = Doctor(str(temp_path))
            assert doctor._has_v2_decorators() is False
            assert doctor.programming_model == "unknown"

    def test_has_v2_decorators_syntax_error_file_skipped(self) -> None:
        """Test that files with SyntaxErrors are gracefully skipped."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bad_file = temp_path / "broken.py"
            bad_file.write_text("def (invalid syntax!!!")
            doctor = Doctor(str(temp_path))
            assert doctor._has_v2_decorators() is False
            assert doctor.programming_model == "unknown"

    def test_run_all_checks_short_circuits_on_unsupported_v1(self) -> None:
        """Test unsupported v1 projects return a single programming_model failure."""
        doctor = Doctor(str(FIXTURES_DIR / "v1"))

        with patch("azure_functions_doctor.doctor.generic_handler") as mock_handler:
            results = doctor.run_all_checks()

        assert mock_handler.call_count == 0
        assert results == [
            {
                "title": "Programming Model",
                "category": "programming_model",
                "status": "fail",
                "items": [
                    {
                        "rule_id": "check_programming_model_v2",
                        "label": "Unsupported programming model: Python v1",
                        "value": UNSUPPORTED_V1_VALUE,
                        "status": "fail",
                        "severity": "error",
                        "tier": "core",
                        "hint": UNSUPPORTED_V1_HINT,
                        "analysis": {"type": "deterministic"},
                    }
                ],
            }
        ]

    def test_run_all_checks_short_circuits_on_unknown(self) -> None:
        """Test projects without v2 signals return a single programming_model failure."""
        doctor = Doctor(str(FIXTURES_DIR / "unknown"))

        with patch("azure_functions_doctor.doctor.generic_handler") as mock_handler:
            results = doctor.run_all_checks()

        assert mock_handler.call_count == 0
        assert results == [
            {
                "title": "Programming Model",
                "category": "programming_model",
                "status": "fail",
                "items": [
                    {
                        "rule_id": "check_programming_model_v2",
                        "label": "Python v2 programming model was not detected",
                        "value": UNKNOWN_VALUE,
                        "status": "fail",
                        "severity": "error",
                        "tier": "core",
                        "hint": UNKNOWN_HINT,
                        "analysis": {"type": "deterministic"},
                    }
                ],
            }
        ]

    def test_venv_function_json_does_not_trigger_v1_or_mixed(self) -> None:
        """A function.json inside a virtualenv must not create false v1/mixed signals."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Valid v2 project at the root.
            (temp_path / "function_app.py").write_text(
                """
import azure.functions as func

app = func.FunctionApp()

@app.route(route=\"test\", auth_level=func.AuthLevel.Anonymous)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(\"Hello\")
"""
            )

            # A stray legacy function.json vendored inside a non-dot ``venv`` dir.
            venv_func = temp_path / "venv" / "lib" / "legacy"
            venv_func.mkdir(parents=True)
            (venv_func / "function.json").write_text('{"bindings": []}')

            doctor = Doctor(str(temp_path))
            # venv-hosted function.json must be ignored: no v1 signal, no mixed model.
            assert doctor._has_v1_signals() is False
            assert doctor.programming_model == "v2"

    def test_excluded_dirs_cover_common_venv_and_cache_names(self) -> None:
        """Guard the exclusion set against regressions for common vendor/cache dirs."""
        from azure_functions_doctor.handlers._helpers import EXCLUDED_PROJECT_DIRS

        expected = {
            ".venv",
            "venv",
            "env",
            "site-packages",
            "node_modules",
            ".tox",
            ".nox",
            ".mypy_cache",
            ".ruff_cache",
            ".git",
        }
        assert expected <= EXCLUDED_PROJECT_DIRS
