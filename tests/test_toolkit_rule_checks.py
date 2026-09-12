"""Tests for the DX-toolkit heuristic rule checks (issue #234).

Covers five rule types added for the Azure Functions Python DX Toolkit:
``openapi_version_mixing``, ``scan_before_spec``, ``langgraph_anonymous_auth``,
``durable_nondeterminism`` and ``unsupported_metadata_version`` -- exercising
both the pure AST/JSON helper functions and their ``HandlerRegistry`` handlers.
"""

from importlib import import_module
from pathlib import Path
from typing import Any, cast

from azure_functions_doctor.handlers._helpers import (
    Rule,
    _collect_anonymous_auth_routes,
    _collect_openapi_version_mixing,
    _collect_orchestrator_nondeterminism,
    _collect_scan_before_spec,
    _collect_unsupported_metadata_versions,
    _dotted_call_name,
    _project_activates_trace_context,
    _project_declares_opentelemetry,
    _project_imports_langgraph,
)
from azure_functions_doctor.handlers.registry import HandlerRegistry

registry = HandlerRegistry()


def _write(path: Path, name: str, content: str) -> None:
    (path / name).write_text(content, encoding="utf-8")


def _status(rule_type: str, path: Path, condition: dict[str, Any] | None = None) -> str:
    rule = cast(
        Rule,
        {"type": rule_type, "required": False, "condition": condition or {}},
    )
    return registry.handle(rule, path)["status"]


# ---------------------------------------------------------------------------
# _dotted_call_name
# ---------------------------------------------------------------------------


def test_dotted_call_name_variants() -> None:
    import ast

    def _call(src: str) -> ast.expr:
        node = ast.parse(src, mode="eval").body
        assert isinstance(node, ast.Call)
        return node.func

    assert _dotted_call_name(_call("open('x')")) == "open"
    assert _dotted_call_name(_call("random.randint(1, 2)")) == "random.randint"
    assert _dotted_call_name(_call("a.b.c.d()")) == "a.b.c.d"
    # Non-name/attribute target (subscript) -> None
    assert _dotted_call_name(_call("registry[0]()")) is None


# ---------------------------------------------------------------------------
# openapi_version_mixing
# ---------------------------------------------------------------------------


def test_openapi_version_mixing_both_signals_fails(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "app.py",
        "V30 = '3.0.3'\nV31 = '3.1.0'\n",
    )
    assert _collect_openapi_version_mixing(tmp_path) == {
        "3.0": {"3.0.3"},
        "3.1": {"3.1.0"},
        "3.2": set(),
    }
    assert _status("openapi_version_mixing", tmp_path) == "fail"


def test_openapi_version_mixing_nullable_counts_as_v30(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "app.py",
        "def f():\n    schema(nullable=True)\n    return '3.1.0'\n",
    )
    signals = _collect_openapi_version_mixing(tmp_path)
    assert "nullable" in signals["3.0"] and "3.1.0" in signals["3.1"]

    assert _status("openapi_version_mixing", tmp_path) == "fail"


def test_openapi_version_mixing_single_version_passes(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "V = '3.1.0'\n")
    assert _status("openapi_version_mixing", tmp_path) == "pass"


def test_openapi_version_mixing_32_only_passes(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "V = '3.2.0'\n")
    assert _collect_openapi_version_mixing(tmp_path)["3.2"] == {"3.2.0"}
    assert _status("openapi_version_mixing", tmp_path) == "pass"


def test_openapi_version_mixing_31_and_32_fails(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "V31 = '3.1.0'\nV32 = '3.2.0'\n")
    assert _status("openapi_version_mixing", tmp_path) == "fail"


def test_openapi_version_mixing_skips_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def f(:\n")
    assert _collect_openapi_version_mixing(tmp_path) == {"3.0": set(), "3.1": set(), "3.2": set()}


# ---------------------------------------------------------------------------
# scan_before_spec
# ---------------------------------------------------------------------------


def test_scan_before_spec_spec_before_scan_fails(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions-openapi==0.24.0\n")
    _write(
        tmp_path,
        "app.py",
        "build_spec()\nscan()\n",
    )
    scan = {"scan"}
    spec = {"build_spec"}
    assert _collect_scan_before_spec(tmp_path, scan, spec)[0] == ["app.py:build_spec"]
    assert _status("scan_before_spec", tmp_path) == "fail"


def test_scan_before_spec_correct_order_passes(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions-openapi==0.24.0\n")
    _write(tmp_path, "app.py", "scan()\nbuild_spec()\n")
    assert _status("scan_before_spec", tmp_path) == "pass"


def test_scan_before_spec_spec_without_scan_fails(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions-openapi==0.24.0\n")
    _write(tmp_path, "app.py", "build_spec()\n")
    assert _collect_scan_before_spec(tmp_path, {"scan"}, {"build_spec"})[0] == ["app.py:build_spec"]
    assert _status("scan_before_spec", tmp_path) == "fail"


def test_scan_before_spec_no_spec_passes(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "scan()\n")
    assert _collect_scan_before_spec(tmp_path, {"scan"}, {"build_spec"})[0] == []


def test_scan_before_spec_custom_names(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions-openapi==0.24.0\n")
    _write(tmp_path, "app.py", "make_spec()\ndiscover()\n")
    assert (
        _status(
            "scan_before_spec",
            tmp_path,
            {"scan_names": ["discover"], "spec_names": ["make_spec"]},
        )
        == "fail"
    )


def test_scan_before_spec_skips_without_openapi_dependency(tmp_path: Path) -> None:
    """Non-OpenAPI build() calls (e.g. durable-graph .build()) must not trip (#426)."""
    _write(tmp_path, "app.py", "graph = GraphBuilder(nodes).build()\n")
    _write(tmp_path, "requirements.txt", "azure-functions-durable-graph==0.3.0\n")
    assert _status("scan_before_spec", tmp_path) == "skip"


def test_scan_before_spec_real_openapi_names_default_condition(tmp_path: Path) -> None:
    # Regression (#248): the real azure-functions-openapi call names must be
    # recognised by the built-in default names baked into the handler, so the
    # rule fires even though v2.json's condition does not re-list them.
    _write(tmp_path, "requirements.txt", "azure-functions-openapi==0.24.0\n")
    _write(
        tmp_path,
        "app.py",
        "get_openapi_json()\nscan_endpoint_metadata()\n",
    )
    assert _status("scan_before_spec", tmp_path) == "fail"


def test_scan_before_spec_real_openapi_names_correct_order_passes(tmp_path: Path) -> None:
    # Regression (#248): scanning before building the spec passes with defaults.
    _write(tmp_path, "requirements.txt", "azure-functions-openapi==0.24.0\n")
    _write(
        tmp_path,
        "app.py",
        "scan_endpoint_metadata()\ngenerate_openapi_spec()\n",
    )
    assert _status("scan_before_spec", tmp_path) == "pass"


def test_scan_before_spec_skips_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def f(:\n")
    assert _collect_scan_before_spec(tmp_path, {"scan"}, {"build_spec"})[0] == []


def test_scan_before_spec_dotted_call_target(tmp_path: Path) -> None:
    # attribute-style call that resolves to a leaf name is still matched
    _write(tmp_path, "app.py", "api.build_spec()\napi.scan()\n")
    assert _collect_scan_before_spec(tmp_path, {"scan"}, {"build_spec"})[0] == ["app.py:build_spec"]


# ---------------------------------------------------------------------------
# langgraph_anonymous_auth
# ---------------------------------------------------------------------------


def test_project_imports_langgraph_detection(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "import langgraph\n")
    assert _project_imports_langgraph(tmp_path) is True


def test_project_imports_langgraph_from_import(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "from langgraph.graph import StateGraph\n")
    assert _project_imports_langgraph(tmp_path) is True


def test_project_imports_langgraph_absent(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "import os\n")
    assert _project_imports_langgraph(tmp_path) is False


def test_project_imports_langgraph_skips_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def f(:\n")
    assert _project_imports_langgraph(tmp_path) is False


def _langgraph_app(route_line: str) -> str:
    return (
        "import langgraph\n"
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        f"{route_line}\n"
        "def handler(req):\n"
        "    return req\n"
    )


def test_langgraph_anonymous_auth_attribute_fails(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        _langgraph_app("@app.route(route='x', auth_level=func.AuthLevel.ANONYMOUS)"),
    )
    assert [lbl for lbl, _ln in _collect_anonymous_auth_routes(tmp_path)] == [
        "function_app.py:handler"
    ]
    assert _status("langgraph_anonymous_auth", tmp_path) == "fail"


def test_langgraph_anonymous_auth_string_fails(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        _langgraph_app("@app.route(route='x', auth_level='anonymous')"),
    )
    assert _status("langgraph_anonymous_auth", tmp_path) == "fail"


def test_langgraph_anonymous_auth_function_level_passes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        _langgraph_app("@app.route(route='x', auth_level=func.AuthLevel.FUNCTION)"),
    )
    assert _status("langgraph_anonymous_auth", tmp_path) == "pass"


def test_langgraph_anonymous_auth_skipped_without_langgraph(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        "@app.route(route='x', auth_level=func.AuthLevel.ANONYMOUS)\n"
        "def handler(req):\n"
        "    return req\n",
    )
    assert _status("langgraph_anonymous_auth", tmp_path) == "skip"


def test_langgraph_anonymous_auth_flag_missing(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        _langgraph_app("@app.route(route='x')"),
    )
    assert _collect_anonymous_auth_routes(tmp_path) == []
    assert [
        lbl for lbl, _ln in _collect_anonymous_auth_routes(tmp_path, flag_missing_auth_level=True)
    ] == ["function_app.py:handler"]


def test_langgraph_anonymous_auth_skips_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "@app.route(\n")
    assert _collect_anonymous_auth_routes(tmp_path) == []


# ---------------------------------------------------------------------------
# durable_nondeterminism
# ---------------------------------------------------------------------------

_BLOCK = {"datetime.now", "random.randint", "uuid.uuid4"}
_DECOS = {"orchestration_trigger"}


def test_durable_nondeterminism_flags_calls(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        "@app.orchestration_trigger(context_name='context')\n"
        "def orch(context):\n"
        "    x = random.randint(1, 9)\n"
        "    return x\n",
    )
    flagged = _collect_orchestrator_nondeterminism(tmp_path, _BLOCK, _DECOS)
    assert [lbl for lbl, _ln in flagged] == ["function_app.py:orch -> random.randint"]
    assert _status("durable_nondeterminism", tmp_path) == "fail"


def test_durable_nondeterminism_clean_orchestrator_passes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        "@app.orchestration_trigger(context_name='context')\n"
        "def orch(context):\n"
        "    return context.call_activity('a', None)\n",
    )
    assert _status("durable_nondeterminism", tmp_path) == "pass"


def test_durable_nondeterminism_ignores_non_orchestrator(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        "def helper():\n    return random.randint(1, 2)\n",
    )
    assert _collect_orchestrator_nondeterminism(tmp_path, _BLOCK, _DECOS) == []


def test_durable_nondeterminism_dotted_suffix_match(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        "@app.orchestration_trigger(context_name='context')\n"
        "def orch(context):\n"
        "    return datetime.datetime.now()\n",
    )
    flagged = _collect_orchestrator_nondeterminism(tmp_path, {"datetime.now"}, _DECOS)
    assert [lbl for lbl, _ln in flagged] == ["function_app.py:orch -> datetime.datetime.now"]


def test_durable_nondeterminism_skips_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def f(:\n")
    assert _collect_orchestrator_nondeterminism(tmp_path, _BLOCK, _DECOS) == []


# ---------------------------------------------------------------------------
# unsupported_metadata_version
# ---------------------------------------------------------------------------

_META_COND = {
    "files": ["*.meta.json"],
    "fields": ["metadataVersion"],
    "supported_versions": ["1.0", "2.0"],
}


def test_unsupported_metadata_version_host_json_fails(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "host.json",
        '{"extensionBundle": {"version": "9.9"}}',
    )
    found = _collect_unsupported_metadata_versions(tmp_path, [], [], ["1.0"])
    assert found == [("host.json:extensionBundle.version", "9.9")]
    assert (
        _status("unsupported_metadata_version", tmp_path, {"supported_versions": ["1.0"]}) == "fail"
    )


def test_unsupported_metadata_version_meta_file_fails(tmp_path: Path) -> None:
    _write(tmp_path, "bindings.meta.json", '{"metadataVersion": "9.9"}')
    found = _collect_unsupported_metadata_versions(
        tmp_path, ["*.meta.json"], ["metadataVersion"], ["1.0", "2.0"]
    )
    assert found == [("bindings.meta.json:metadataVersion", "9.9")]
    assert _status("unsupported_metadata_version", tmp_path, _META_COND) == "fail"


def test_unsupported_metadata_version_supported_passes(tmp_path: Path) -> None:
    _write(tmp_path, "bindings.meta.json", '{"metadataVersion": "2.0"}')
    assert _status("unsupported_metadata_version", tmp_path, _META_COND) == "pass"


def test_unsupported_metadata_version_no_config_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "host.json", '{"extensionBundle": {"version": "9.9"}}')
    # empty supported_versions -> check is skipped (pass)
    assert _status("unsupported_metadata_version", tmp_path) == "skip"


def test_unsupported_metadata_version_malformed_json_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "host.json", "{ not json")
    _write(tmp_path, "bad.meta.json", "{ not json")
    found = _collect_unsupported_metadata_versions(
        tmp_path, ["*.meta.json"], ["metadataVersion"], ["1.0"]
    )
    assert found == []


def test_unsupported_metadata_version_missing_field_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "bindings.meta.json", '{"other": "9.9"}')
    found = _collect_unsupported_metadata_versions(
        tmp_path, ["*.meta.json"], ["metadataVersion"], ["1.0"]
    )
    assert found == []


# ---------------------------------------------------------------------------
# End-to-end: rules load and run through Doctor
# ---------------------------------------------------------------------------


def test_new_rules_present_in_doctor_output(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "function_app.py",
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        "@app.route(route='x')\n"
        "def handler(req):\n"
        "    return req\n",
    )
    _write(tmp_path, "host.json", '{"version": "2.0"}')
    _write(tmp_path, "requirements.txt", "azure-functions\n")
    doctor_cls = import_module("azure_functions_doctor.doctor").Doctor
    results = doctor_cls(str(tmp_path)).run_all_checks()
    labels = {item["label"] for section in results for item in section["items"]}
    for label in (
        "OpenAPI version consistency",
        "Endpoint scan before spec build",
        "LangGraph route authentication",
        "Orchestrator determinism",
        "OTel trace-context activation",
    ):
        assert label in labels


# ---------------------------------------------------------------------------
# otel_activation
# ---------------------------------------------------------------------------


def test_project_activates_trace_context_keyword(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.py",
        "from azure_functions_logging import setup_logging\n"
        "setup_logging(activate_trace_context=True)\n",
    )
    assert _project_activates_trace_context(tmp_path)


def test_project_activates_trace_context_setter_call(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.py",
        "from azure_functions_logging import set_default_trace_context_activation\n"
        "set_default_trace_context_activation(True)\n",
    )
    assert _project_activates_trace_context(tmp_path)


def test_project_activates_trace_context_setter_bare_call(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "set_default_trace_context_activation()\n")
    assert _project_activates_trace_context(tmp_path)


def test_project_activates_trace_context_setter_enabled_keyword(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "set_default_trace_context_activation(enabled=True)\n")
    assert _project_activates_trace_context(tmp_path)


def test_project_activates_trace_context_false_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "setup_logging(activate_trace_context=False)\n")
    assert not _project_activates_trace_context(tmp_path)
    _write(tmp_path, "b.py", "set_default_trace_context_activation(False)\n")
    assert not _project_activates_trace_context(tmp_path)


def test_project_activates_trace_context_skips_syntax_error(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "def broken(:\n")
    assert not _project_activates_trace_context(tmp_path)


def test_project_declares_opentelemetry_requirements(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "opentelemetry-api>=1.24\n")
    assert _project_declares_opentelemetry(tmp_path)


def test_project_declares_opentelemetry_pyproject(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["opentelemetry-sdk>=1.24"]\n',
    )
    assert _project_declares_opentelemetry(tmp_path)


def test_project_declares_opentelemetry_absent(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions\n")
    assert not _project_declares_opentelemetry(tmp_path)


def test_otel_activation_without_dependency_fails(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "setup_logging(activate_trace_context=True)\n")
    _write(tmp_path, "requirements.txt", "azure-functions\n")
    assert _status("otel_activation", tmp_path) == "fail"


def test_otel_activation_with_dependency_passes(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "setup_logging(activate_trace_context=True)\n")
    _write(tmp_path, "requirements.txt", "azure-functions\nopentelemetry-api>=1.24\n")
    assert _status("otel_activation", tmp_path) == "pass"


def test_otel_activation_no_activation_passes(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "import os\n")
    assert _status("otel_activation", tmp_path) == "skip"
