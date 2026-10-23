import ast
import json
import logging
from pathlib import Path
import sys
import time
from unittest.mock import patch

import pytest

from azure_functions_doctor.agent import AgentReportError, load_agent_report
from azure_functions_doctor.deploy_config import resolve_target_config
from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers._helpers import (
    _iter_project_py_contents,
    _load_pyproject,
    _read_project_python_file,
    _source_contains_ast,
)
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps


@pytest.mark.parametrize("stage", ["parse", "walk"])
@pytest.mark.parametrize("failure", [RecursionError, MemoryError, ValueError])
def test_inventory_python_parser_failure_is_visible(
    tmp_path: Path, stage: str, failure: type[Exception]
) -> None:
    (tmp_path / "app.py").write_text("app=func.FunctionApp()")
    with collect_inspection_gaps() as gaps:
        with patch.object(ast, stage, side_effect=failure("CANARY_PARSER")):
            for _, content in _iter_project_py_contents(tmp_path):
                _source_contains_ast(content, "app")
    assert gaps


@pytest.mark.parametrize("filename", ["host.json", "infra.json", "local.settings.json"])
def test_inventory_json_depth_is_refused_before_deserialization(
    tmp_path: Path, filename: str
) -> None:
    (tmp_path / filename).write_text("[" * 101 + "0" + "]" * 101)
    with collect_inspection_gaps() as gaps:
        resolve_target_config(tmp_path)
    assert gaps


def test_inventory_json_escaped_quote_scan_is_linear(tmp_path: Path) -> None:
    (tmp_path / "infra.json").write_text('"' + '\\"' * 100_000)
    start = time.monotonic()
    resolve_target_config(tmp_path)
    assert time.monotonic() - start < 2


@pytest.mark.parametrize(
    "content", ["x=1\nx=2", "x=" + "[" * 2000 + "0" + "]" * 2000], ids=["duplicate", "deep"]
)
def test_inventory_toml_parser_failure_is_visible(tmp_path: Path, content: str) -> None:
    (tmp_path / "pyproject.toml").write_text(content)
    with collect_inspection_gaps() as gaps:
        assert _load_pyproject(tmp_path) is None
    assert gaps


@pytest.mark.parametrize("kind", ["large", "deep", "binary", "symlink"])
def test_inventory_agent_refuses_hostile_reports(tmp_path: Path, kind: str) -> None:
    report = tmp_path / "report.json"
    if kind == "large":
        report.write_text(" " * (4 * 1024 * 1024) + '{"schema_version":"2.0","results":[]}')
    elif kind == "deep":
        report.write_text(
            '{"schema_version":"2.0","results":[],"ignored":' + "[" * 101 + "0" + "]" * 101 + "}"
        )
    elif kind == "binary":
        report.write_bytes(b"\xffCANARY")
    else:
        outside = tmp_path / "outside.json"
        outside.write_text('{"schema_version":"2.0","results":[]}')
        report.symlink_to(outside)
    with pytest.raises(AgentReportError):
        load_agent_report(report)


def test_inventory_trusted_bundled_rules_load_normally(tmp_path: Path) -> None:
    assert Doctor(str(tmp_path)).load_rules()


@pytest.mark.parametrize("reader", ["source", "toml"])
def test_inventory_helper_debug_logs_do_not_echo_content_or_filename(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, reader: str
) -> None:
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    token = "CANARY_SECRET_HELPER"
    if reader == "source":
        source = tmp_path / (token + ".py")
        source.write_bytes(b"\xff")
        assert _read_project_python_file(source) is None
    else:
        (tmp_path / "pyproject.toml").write_text(f"{token}=1\n{token}=2")
        assert _load_pyproject(tmp_path) is None
    assert token not in caplog.text


@pytest.mark.parametrize("kind", ["any_of_exists", "app_insights_connection"])
def test_inventory_host_debug_logs_omit_exception_payload(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, kind: str
) -> None:
    (tmp_path / "host.json").write_text("invalid")
    token = "CANARY_SECRET_JSON_ERROR"
    rule = next(rule for rule in Doctor(str(tmp_path)).load_rules() if rule.get("type") == kind)
    if kind == "any_of_exists":
        rule["condition"] = {"targets": ["host.json:version"]}
    caplog.set_level(logging.DEBUG, logger="azure_functions_doctor")
    with patch.object(json, "loads", side_effect=json.JSONDecodeError(token, "", 0)):
        HandlerRegistry().handle(rule, tmp_path)
    assert token not in caplog.text


def test_inventory_agent_exception_omits_parser_payload(tmp_path: Path) -> None:
    report = tmp_path / "CANARY_SECRET_PATH.json"
    report.write_text("invalid")
    with pytest.raises(AgentReportError) as error:
        load_agent_report(report)
    assert "CANARY_SECRET_PATH" not in str(error.value)


def test_inventory_external_references_are_not_resolved(tmp_path: Path) -> None:
    token = "CANARY_EXTERNAL_RESOLVER"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "module.bicep").write_text(f"linuxFxVersion: '{token}'")
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.bicep").write_text(
        "module other '../outside/module.bicep' = {}\n"
        "var secret = loadTextContent('../outside/secret.txt')\n"
    )
    (outside / "secret.txt").write_text(token)
    (project / "host.json").write_text('{"$ref":"../outside/host.json"}')
    (outside / "host.json").write_text('{"Values":{"secret":"' + token + '"}}')
    assert token not in repr(resolve_target_config(project))


def test_inventory_no_shell_execution_in_runtime_commands() -> None:
    import azure_functions_doctor.handlers.deployment as deployment
    import azure_functions_doctor.target_resolver as target

    assert sys.modules[target.__name__] is target
    for module in (deployment, target):
        tree = ast.parse(Path(str(module.__file__)).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert not any(
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                )
