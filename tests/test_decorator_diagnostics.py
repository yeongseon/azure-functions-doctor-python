from importlib import import_module
from pathlib import Path

from typer.testing import CliRunner

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "v2"
runner = CliRunner()


def _item_status_by_label(project_path: Path) -> dict[str, str]:
    doctor_cls = import_module("azure_functions_doctor.doctor").Doctor
    results = doctor_cls(str(project_path)).run_all_checks()
    return {item["label"]: item["status"] for section in results for item in section["items"]}


# ---------------------------------------------------------------------------
# Decorator order (fixture-driven)
# ---------------------------------------------------------------------------


def test_decorator_order_correct_passes() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "decorator_order_correct")
    assert item_map["Decorator order"] == "pass"


def test_decorator_order_inverted_warns() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "decorator_order_inverted")
    assert item_map["Decorator order"] == "warn"


# ---------------------------------------------------------------------------
# Endpoint metadata coverage (fixture-driven)
# ---------------------------------------------------------------------------


def test_endpoint_metadata_covered_passes() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "endpoint_metadata_covered")
    assert item_map["Endpoint metadata coverage"] == "pass"


def test_endpoint_metadata_missing_warns() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "endpoint_metadata_missing")
    assert item_map["Endpoint metadata coverage"] == "warn"


def test_endpoint_metadata_no_dep_passes() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "endpoint_metadata_no_dep")
    assert item_map["Endpoint metadata coverage"] == "skip"


# ---------------------------------------------------------------------------
# CLI output detail
# ---------------------------------------------------------------------------


def test_cli_shows_decorator_order_fix_detail() -> None:
    cli_app = import_module("azure_functions_doctor.cli").cli
    result = runner.invoke(
        cli_app,
        [
            "doctor",
            "--path",
            str(FIXTURES_DIR / "decorator_order_inverted"),
            "--format",
            "table",
            "--verbose",
        ],
    )
    assert result.exit_code == 0
    assert "Decorator order" in result.output
    assert "Inverted decorator order detected" in result.output


# ---------------------------------------------------------------------------
# Unit tests: _decorator_simple_name
# ---------------------------------------------------------------------------


def test_decorator_simple_name_variants() -> None:
    import ast

    helpers = import_module("azure_functions_doctor.handlers._helpers")

    def _first_decorator(src: str) -> ast.expr:
        tree = ast.parse(src)
        func_node = tree.body[0]
        assert isinstance(func_node, ast.FunctionDef)
        return func_node.decorator_list[0]

    # bare @name
    assert helpers._decorator_simple_name(
        _first_decorator("@validate_http\ndef f():\n    ...")
    ) == ("validate_http")
    # attribute @mod.name
    assert helpers._decorator_simple_name(
        _first_decorator("@m.validate_http\ndef f():\n    ...")
    ) == ("validate_http")
    # call @mod.name(...)
    assert (
        helpers._decorator_simple_name(_first_decorator("@app.route(route='x')\ndef f():\n    ..."))
        == "route"
    )
    # subscript decorator -> None
    assert helpers._decorator_simple_name(_first_decorator("@reg[0]\ndef f():\n    ...")) is None


# ---------------------------------------------------------------------------
# Unit tests: _collect_inverted_decorator_order edge cases
# ---------------------------------------------------------------------------

#: Default outermost-first order shipped in the decorator_order rule.
_ORDER = ["with_context", "validate_http"]
# ---------------------------------------------------------------------------


def test_collect_inverted_decorator_order_only_one_decorator(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "@validate_http\ndef f():\n    return None\n", encoding="utf-8"
    )
    assert helpers._collect_inverted_decorator_order(tmp_path, _ORDER) == []


def test_collect_inverted_decorator_order_async_function(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "@app.route(route='x')\n@validate_http\n@with_context\nasync def f():\n    return None\n",
        encoding="utf-8",
    )
    assert [lbl for lbl, _ln in helpers._collect_inverted_decorator_order(tmp_path, _ORDER)] == [
        "function_app.py:f"
    ]


def test_collect_inverted_decorator_order_skips_syntax_error(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")
    assert helpers._collect_inverted_decorator_order(tmp_path, _ORDER) == []


def test_collect_inverted_decorator_order_honors_custom_order(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    # @a stacked above @b; with expected order [b, a] this is inverted.
    (tmp_path / "function_app.py").write_text(
        "@a\n@b\ndef f():\n    return None\n", encoding="utf-8"
    )
    assert helpers._collect_inverted_decorator_order(tmp_path, ["a", "b"]) == []
    assert [
        lbl for lbl, _ln in helpers._collect_inverted_decorator_order(tmp_path, ["b", "a"])
    ] == ["function_app.py:f"]


# ---------------------------------------------------------------------------
# Unit tests: endpoint metadata helpers
# ---------------------------------------------------------------------------


def test_project_declares_validation_dep_missing_requirements(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    assert helpers._project_declares_validation_dep(tmp_path) is False


def test_project_declares_validation_dep_present(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "requirements.txt").write_text(
        "azure-functions\nazure-functions-validation>=0.1\n", encoding="utf-8"
    )
    assert helpers._project_declares_validation_dep(tmp_path) is True


def test_collect_routes_missing_validate_http_skips_syntax_error(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "broken.py").write_text("@app.route(\n", encoding="utf-8")
    assert helpers._collect_routes_missing_validate_http(tmp_path) == []


def test_collect_routes_missing_validate_http_custom_alias(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "fa = func.FunctionApp()\n\n"
        "@fa.route(route='x')\n"
        "def handler(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert helpers._collect_routes_missing_validate_http(tmp_path) == ["function_app.py:handler"]


def test_collect_routes_missing_validate_http_excludes_spec_serving(tmp_path: Path) -> None:
    # A spec-serving route (returns the OpenAPI document) must not be flagged for
    # missing @validate_http, while a genuine data route still is.
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from azure_functions_openapi import get_openapi_json\n"
        "fa = func.FunctionApp()\n\n"
        "@fa.route(route='openapi.json')\n"
        "def openapi_doc(req):\n"
        "    return get_openapi_json()\n\n"
        "@fa.route(route='items')\n"
        "def items(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert helpers._collect_routes_missing_validate_http(tmp_path) == ["function_app.py:items"]


def test_collect_routes_openapi_decorator_covers_metadata(tmp_path: Path) -> None:
    # A route carrying @openapi already emits endpoint metadata, so it must not
    # be flagged even without @validate_http.
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from azure_functions_openapi import openapi\n"
        "fa = func.FunctionApp()\n\n"
        "@fa.route(route='items')\n"
        "@openapi(summary='List items')\n"
        "def items(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert helpers._collect_routes_missing_validate_http(tmp_path) == []


# ---------------------------------------------------------------------------
# Regression: @validate_http above a binding decorator (dead handler)
# ---------------------------------------------------------------------------


def test_collect_inverted_flags_validate_http_above_binding(tmp_path: Path) -> None:
    # @validate_http above @app.durable_client_input (no @with_context present):
    # validation receives a FunctionBuilder and is silently inactive.
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        "@validate_http\n"
        "@app.durable_client_input(client_name='client')\n"
        "def handler(req, client):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert [lbl for lbl, _ln in helpers._collect_inverted_decorator_order(tmp_path, _ORDER)] == [
        "function_app.py:handler"
    ]


def test_collect_inverted_ignores_validate_http_below_binding(tmp_path: Path) -> None:
    # Correct order: @app.route outermost, @validate_http innermost -> active.
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        "@app.route(route='x')\n"
        "@validate_http\n"
        "def handler(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert helpers._collect_inverted_decorator_order(tmp_path, _ORDER) == []


def test_collect_routes_flags_inactive_validate_http_above_route(tmp_path: Path) -> None:
    # @validate_http declared but placed ABOVE @app.route -> inactive, so the
    # route emits no endpoint metadata even though the name is present.
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        "@validate_http\n"
        "@app.route(route='x')\n"
        "def handler(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert helpers._collect_routes_missing_validate_http(tmp_path) == ["function_app.py:handler"]


def test_collect_routes_passes_active_validate_http_below_route(tmp_path: Path) -> None:
    helpers = import_module("azure_functions_doctor.handlers._helpers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n\n"
        "@app.route(route='x')\n"
        "@validate_http\n"
        "def handler(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    assert helpers._collect_routes_missing_validate_http(tmp_path) == []
