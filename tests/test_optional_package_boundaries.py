from pathlib import Path
from typing import Literal

import pytest

from azure_functions_doctor.handlers import Rule, generic_handler
from azure_functions_doctor.package_evidence import declares_package


@pytest.mark.parametrize("handler", ["decorator_order", "otel_activation"])
def test_unrelated_same_named_features_do_not_warn(
    tmp_path: Path, handler: Literal["decorator_order", "otel_activation"]
) -> None:
    (tmp_path / "function_app.py").write_text(
        "@validate_http\n@with_context\ndef unrelated(): pass\n"
        "setup_logging(activate_trace_context=True)\n",
        encoding="utf-8",
    )
    rule: Rule = {
        "id": "check_decorator_order"
        if handler == "decorator_order"
        else "check_otel_trace_context_activation",
        "type": handler,
    }

    result = generic_handler(rule, tmp_path)

    assert result["status"] == "skip"


@pytest.mark.parametrize(
    "source",
    [
        "import azure_functions_validation as av\n",
        "from azure_functions_validation import validate_http as validate\n",
        "from azure_functions_validation.http import validate_http\n",
    ],
)
def test_import_aliases_are_clear_package_evidence(tmp_path: Path, source: str) -> None:
    (tmp_path / "functions.py").write_text(source, encoding="utf-8")
    assert declares_package(tmp_path, "azure-functions-validation")


def test_invalid_source_does_not_hide_declared_package(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(\n", encoding="utf-8")
    assert not declares_package(tmp_path, "azure-functions-validation")
    (tmp_path / "requirements.txt").write_text(
        "azure-functions-validation==1.0\n", encoding="utf-8"
    )
    assert declares_package(tmp_path, "azure-functions-validation")


def test_builtin_decorator_rule_retains_blueprint_warning_with_import_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from azure_functions_validation import validate_http\n"
        "bp = func.Blueprint()\n"
        "@validate_http\n@bp.route(route='test')\ndef handler(req): pass\n",
        encoding="utf-8",
    )
    result = generic_handler({"id": "check_decorator_order", "type": "decorator_order"}, tmp_path)
    assert result["status"] == "fail"
    assert result["file"] == "function_app.py"


def test_builtin_otel_rule_retains_warning_with_logging_import(tmp_path: Path) -> None:
    (tmp_path / "function_app.py").write_text(
        "from azure_functions_logging import setup_logging\n"
        "setup_logging(activate_trace_context=True)\n",
        encoding="utf-8",
    )
    result = generic_handler(
        {"id": "check_otel_trace_context_activation", "type": "otel_activation"}, tmp_path
    )
    assert result["status"] == "fail"
