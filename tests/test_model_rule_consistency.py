"""The full CLI report must use the same model decision as its preflight gate."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli as app
from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers import Rule


@pytest.mark.parametrize(
    ("source", "legacy", "model", "status"),
    [
        pytest.param(
            "from azure_functions_langgraph import LangGraphApp\n"
            "adapter = LangGraphApp()\napp = adapter.function_app\n",
            False,
            "v2",
            "pass",
            id="adapter-export",
        ),
        pytest.param(
            "from azure_functions_langgraph import LangGraphApp as Adapter\n"
            "adapter = Adapter()\napp = adapter.function_app\n",
            False,
            "v2",
            "pass",
            id="aliased-adapter-export",
        ),
        pytest.param(
            "import azure.functions as func\napp = func.FunctionApp()\n",
            False,
            "v2",
            "pass",
            id="sdk-without-decorators",
        ),
        pytest.param(
            "import azure.functions as func\napp = func.FunctionApp()\n"
            "@app.route(route='health')\ndef health(req): return 'ok'\n",
            False,
            "v2",
            "pass",
            id="ordinary-sdk",
        ),
        pytest.param(
            "from azure.functions import FunctionApp as FA, Blueprint as BP\n"
            "application = FA()\nroutes = BP()\n"
            "@routes.route(route='health')\ndef health(req): return 'ok'\n"
            "application.register_functions(routes)\napp = application\n",
            False,
            "v2",
            "pass",
            id="registered-aliased-blueprint",
        ),
        pytest.param("", True, "unsupported_v1", "fail", id="legacy"),
        pytest.param(
            "import azure.functions as func\napp = func.FunctionApp()\n",
            True,
            "mixed",
            "fail",
            id="mixed",
        ),
        pytest.param(
            "class LangGraphApp:\n    function_app = object()\n"
            "adapter = LangGraphApp()\napp = adapter.function_app\n",
            False,
            "unknown",
            "fail",
            id="unrelated-lookalike",
        ),
    ],
)
def test_full_json_model_rule_agrees_with_preflight(
    tmp_path: Path, source: str, legacy: bool, model: str, status: str
) -> None:
    # Given a project whose source must never be imported during discovery.
    (tmp_path / "function_app.py").write_text(
        "raise RuntimeError('application code must not execute')\n" + source,
        encoding="utf-8",
    )
    (tmp_path / "host.json").write_text('{"version": "2.0"}', encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("azure-functions\n", encoding="utf-8")
    if legacy:
        (tmp_path / "function.json").write_text("{}", encoding="utf-8")

    # When the real CLI evaluates every rule.
    result = CliRunner().invoke(
        app, ["doctor", "--path", str(tmp_path), "--profile", "full", "--format", "json"]
    )

    # Then the report and rule agree, preserving the fail-fast boundary.
    report = json.loads(result.stdout)
    assert report["metadata"]["programming_model"] == model
    findings = [item for section in report["results"] for item in section["items"]]
    model_findings = [item for item in findings if item["rule_id"] == "check_programming_model_v2"]
    assert len(model_findings) == 1
    assert model_findings[0]["status"] == status
    assert model_findings[0]["severity"] == ("warning" if status == "pass" else "error")
    if status == "pass":
        assert len(findings) > 1
    else:
        assert result.exit_code == 1
        assert len(findings) == 1


def test_explicit_rule_with_model_id_keeps_its_condition(tmp_path: Path) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n", encoding="utf-8"
    )
    rule: Rule = {
        "id": "check_programming_model_v2",
        "type": "source_code_contains",
        "section": "custom",
        "required": True,
        "condition": {"keyword": "missing_custom_marker", "mode": "string"},
    }

    results = Doctor(str(tmp_path)).run_all_checks([rule])

    assert results[0]["items"][0]["status"] == "fail"
