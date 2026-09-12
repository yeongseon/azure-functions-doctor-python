"""Tests for v2 rule loading functionality."""

from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from azure_functions_doctor.doctor import Doctor


class TestRuleLoading:
    """Test rule loading logic for the built-in v2 ruleset."""

    @staticmethod
    def _write_v2_app(temp_path: Path) -> None:
        python_file = temp_path / "function_app.py"
        python_file.write_text("""
import azure.functions as func

app = func.FunctionApp()

@app.route(route="test", auth_level=func.AuthLevel.Anonymous)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Hello")
""")

    def test_load_v2_rules(self) -> None:
        """Test loading the built-in v2 rules."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))
            assert doctor.programming_model == "v2"

            rules = doctor.load_rules()
            rule_ids = [rule["id"] for rule in rules]

            assert "check_python_version" in rule_ids
            assert "check_venv" in rule_ids
            assert "check_python_executable" in rule_ids
            assert "check_requirements_txt" in rule_ids
            assert "check_host_json" in rule_ids
            assert "check_local_settings" in rule_ids
            assert "check_azure_functions_library" in rule_ids
            assert "check_programming_model_v2" in rule_ids
            assert "check_http_trigger_bindings" not in rule_ids
            assert "check_timer_cron" not in rule_ids
            # Removed in #311: shipped as a permanent no-op
            # (empty supported_versions) with no authoritative version set.
            assert "check_unsupported_metadata_version" not in rule_ids

    def test_rule_loading_uses_v2_rules_only(self) -> None:
        """Test that rule loading no longer branches on legacy programming models."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))

            with patch("importlib.resources.files") as mock_files:
                mock_files.return_value.joinpath.return_value.open.side_effect = FileNotFoundError()

                with pytest.raises(RuntimeError, match="v2.json not found"):
                    doctor.load_rules()

    def test_rule_loading_handles_json_errors(self) -> None:
        """Test that rule loading handles JSON parsing errors gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))

            with patch("importlib.resources.files") as mock_files:
                mock_v2_path = mock_files.return_value.joinpath.return_value
                mock_v2_path.open.return_value.__enter__.return_value.read.return_value = (
                    "invalid json"
                )

                with pytest.raises(RuntimeError, match="Failed to parse v2.json"):
                    doctor.load_rules()

    def test_rule_loading_handles_missing_v2_rules(self) -> None:
        """Test that rule loading handles missing v2.json gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))

            with patch("importlib.resources.files") as mock_files:
                mock_v2_path = mock_files.return_value.joinpath.return_value
                mock_v2_path.open.side_effect = FileNotFoundError()

                with pytest.raises(RuntimeError, match="v2.json not found"):
                    doctor.load_rules()

    def test_rule_ordering(self) -> None:
        """Test that rules are properly ordered by check_order."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))
            rules = doctor.load_rules()

            check_orders = [rule.get("check_order", 999) for rule in rules]
            assert check_orders == sorted(check_orders)

    def test_integration_rules_are_grouped(self) -> None:
        """The ecosystem-integration rules carry group='integration' (#355)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))
            rules = doctor.load_rules()

            integration_ids = {rule["id"] for rule in rules if rule.get("group") == "integration"}
            assert integration_ids == {
                "check_endpoint_metadata",
                "check_openapi_version_mixing",
                "check_scan_before_spec",
                "check_langgraph_anonymous_auth",
                "check_otel_trace_context_activation",
            }

    def test_core_rules_default_group(self) -> None:
        """Rules without an explicit group are treated as core (#355)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))
            rules = doctor.load_rules()

            # A representative Azure-correctness rule ships no group and is core.
            python_version = next(rule for rule in rules if rule["id"] == "check_python_version")
            assert python_version.get("group", "core") == "core"
            # Every rule's group is one of the two allowed values.
            assert all(rule.get("group", "core") in {"core", "integration"} for rule in rules)

    def test_hint_urls_point_at_central_mechanism_pages(self) -> None:
        """Platform-mechanic rules link to the central mechanism pages (#333)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))
            rules = doctor.load_rules()

            by_id = {rule["id"]: rule for rule in rules}
            binding_section = (
                "https://yeongseon.dev/azure-functions-python/platform"
                "/how-the-worker-binds-handlers/#binding"
            )
            assert by_id["check_decorator_order"]["hint_url"] == binding_section
            assert by_id["check_endpoint_metadata"]["hint_url"] == binding_section
            assert by_id["check_otel_trace_context_activation"]["hint_url"] == (
                "https://yeongseon.dev/azure-functions-python/logging/opentelemetry/"
            )

    def test_rule_loading_with_no_rules_files(self) -> None:
        """Test that rule loading fails gracefully when no rule files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._write_v2_app(temp_path)

            doctor = Doctor(str(temp_path))

            with patch("importlib.resources.files") as mock_files:
                mock_files.return_value.joinpath.return_value.open.side_effect = FileNotFoundError()

                with pytest.raises(RuntimeError, match="v2.json not found"):
                    doctor.load_rules()
