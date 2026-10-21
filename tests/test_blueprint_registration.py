from importlib import import_module
from pathlib import Path

import pytest
from typer.testing import CliRunner

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "v2"
runner = CliRunner()


def _item_status_by_label(project_path: Path) -> dict[str, str]:
    doctor_cls = import_module("azure_functions_doctor.doctor").Doctor
    results = doctor_cls(str(project_path)).run_all_checks()
    return {item["label"]: item["status"] for section in results for item in section["items"]}


def test_collect_blueprint_aliases_finds_blueprint_assignments() -> None:
    handlers = import_module("azure_functions_doctor.handlers")
    source = """
import azure.functions as func

bp = func.Blueprint()
other = Blueprint()
app = func.FunctionApp()
"""
    assert handlers._collect_blueprint_aliases(source) == {"bp", "other"}


def test_collect_register_functions_args_only_accepts_official_api() -> None:
    handlers = import_module("azure_functions_doctor.handlers")
    source = """
import azure.functions as func

app = func.FunctionApp()
app.register_functions(bp)
app.register_blueprint(alias_bp)
loader.register_functions(other_bp)
loader.register_blueprint(flask_bp)
register_blueprint(flask_bare)
app.register_functions(factory())
"""
    assert handlers._collect_register_functions_args(source) == {"alias_bp", "bp"}


def test_blueprint_registration_accepts_function_app_register_blueprint(tmp_path: Path) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "bp = func.Blueprint()\n"
        "@bp.route(route='hello')\n"
        "def hello(req): return req\n"
        "app.register_blueprint(bp)\n",
        encoding="utf-8",
    )

    item_map = _item_status_by_label(tmp_path)

    assert item_map["Blueprint registration"] == "pass"


def test_collect_unregistered_blueprint_aliases_tracks_project_level_registration(
    tmp_path: Path,
) -> None:
    handlers = import_module("azure_functions_doctor.handlers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "bp = func.Blueprint()\n"
        "other_bp = func.Blueprint()\n\n"
        "@bp.route(route='hello')\n"
        "def hello(req):\n"
        "    return req\n\n"
        "@other_bp.route(route='other')\n"
        "def other(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    # loader.py imports bp from function_app.py (#446): registration is
    # tracked by following this real import back to bp's defining module,
    # not by a bare cross-file name match that a same-named blueprint in a
    # third file could otherwise falsely satisfy.
    (tmp_path / "loader.py").write_text(
        "import azure.functions as func\n"
        "from function_app import bp\n"
        "app = func.FunctionApp()\n"
        "app.register_functions(bp)\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == {"other_bp"}


def test_collect_unregistered_blueprint_aliases_skips_excluded_directories(tmp_path: Path) -> None:
    handlers = import_module("azure_functions_doctor.handlers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "bp = func.Blueprint()\n\n"
        "@bp.route(route='hello')\n"
        "def hello(req):\n"
        "    return req\n\n"
        "app.register_functions(bp)\n",
        encoding="utf-8",
    )
    excluded_dir = tmp_path / ".venv"
    excluded_dir.mkdir()
    (excluded_dir / "ignored.py").write_text(
        "import azure.functions as func\n"
        "rogue = func.Blueprint()\n\n"
        "@rogue.route(route='ignored')\n"
        "def ignored(req):\n"
        "    return req\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == set()


def test_collect_unregistered_blueprint_aliases_detects_async_decorated_route(
    tmp_path: Path,
) -> None:
    """An unregistered Blueprint route decorated with `async def` must warn
    exactly as the identical synchronous route does -- the SDK never
    registers this route either way, so the same missing-registration
    warning applies regardless of sync/async (#585)."""
    handlers = import_module("azure_functions_doctor.handlers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "bp = func.Blueprint()\n\n"
        "@bp.route(route='work')\n"
        "async def work(req):\n"
        "    return req\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == {"bp"}


def test_collect_unregistered_blueprint_aliases_passes_when_async_route_registered(
    tmp_path: Path,
) -> None:
    handlers = import_module("azure_functions_doctor.handlers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "app = func.FunctionApp()\n"
        "bp = func.Blueprint()\n\n"
        "@bp.route(route='work')\n"
        "async def work(req):\n"
        "    return req\n\n"
        "app.register_functions(bp)\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == set()


def test_blueprint_registration_fixture_passes_when_registered() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "blueprint_registered")
    assert item_map["Blueprint registration"] == "pass"


def test_blueprint_registration_fixture_warns_when_unregistered() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "blueprint_unregistered")
    assert item_map["Blueprint registration"] == "warn"


@pytest.mark.parametrize(
    "fixture_name",
    ["blueprint_aliased_unregistered", "blueprint_module_aliased_unregistered"],
)
def test_blueprint_registration_fixture_warns_for_aliased_constructors(
    fixture_name: str,
) -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / fixture_name)
    assert item_map["Blueprint registration"] == "warn"


def test_blueprint_registration_fixture_ignores_unrelated_registration() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "blueprint_unrelated_registration")
    assert item_map["Blueprint registration"] == "warn"


def test_blueprint_registration_fixture_skips_when_no_blueprint() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "no_blueprint")
    assert item_map["Blueprint registration"] == "pass"


def test_cli_table_output_shows_blueprint_registration_warning() -> None:
    cli_app = import_module("azure_functions_doctor.cli").cli
    result = runner.invoke(
        cli_app,
        [
            "doctor",
            "--path",
            str(FIXTURES_DIR / "blueprint_unregistered"),
            "--format",
            "table",
        ],
    )

    assert result.exit_code == 0
    assert "Blueprint registration" in result.output
    assert "Detected:" in result.output
    assert "- bp = func.Blueprint()" in result.output
    assert "Missing:" in result.output
    assert "- app.register_functions(bp)" in result.output


# ---------------------------------------------------------------------------
# Module-qualified identity across files (#446)
# ---------------------------------------------------------------------------


def test_same_named_blueprint_in_unregistered_module_still_warns(tmp_path: Path) -> None:
    """first.py and second.py each define 'bp'; only first.bp is registered.
    The bare-name union previously hid second.bp entirely -- this must warn."""
    handlers = import_module("azure_functions_doctor.handlers")
    bp_module = (
        "import azure.functions as func\n"
        "bp = func.Blueprint()\n"
        "@bp.route(route='{route}')\n"
        "def {route}(req):\n"
        "    return req\n"
    )
    (tmp_path / "first.py").write_text(bp_module.format(route="first"), encoding="utf-8")
    (tmp_path / "second.py").write_text(bp_module.format(route="second"), encoding="utf-8")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from first import bp\n"
        "import second\n"
        "app = func.FunctionApp()\n"
        "app.register_functions(bp)\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == {"bp"}


def test_distinct_same_named_blueprints_both_registered_pass(tmp_path: Path) -> None:
    """Both same-named Blueprints (first.bp, second.bp) registered via
    distinct imports must pass -- module-qualified identity must not
    conflate them, but a real registration of each must still be honored."""
    handlers = import_module("azure_functions_doctor.handlers")
    bp_module = (
        "import azure.functions as func\n"
        "bp = func.Blueprint()\n"
        "@bp.route(route='{route}')\n"
        "def {route}(req):\n"
        "    return req\n"
    )
    (tmp_path / "first.py").write_text(bp_module.format(route="first"), encoding="utf-8")
    (tmp_path / "second.py").write_text(bp_module.format(route="second"), encoding="utf-8")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from first import bp\n"
        "from second import bp as second_bp\n"
        "app = func.FunctionApp()\n"
        "app.register_functions(bp)\n"
        "app.register_functions(second_bp)\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == set()


def test_registered_import_alias_resolves_to_origin_pass(tmp_path: Path) -> None:
    """`from first import bp as registered_bp`, then registering that alias,
    must resolve back to first.bp's real identity and pass."""
    handlers = import_module("azure_functions_doctor.handlers")
    (tmp_path / "first.py").write_text(
        "import azure.functions as func\n"
        "bp = func.Blueprint()\n"
        "@bp.route(route='first')\n"
        "def first(req):\n"
        "    return req\n",
        encoding="utf-8",
    )
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "from first import bp as registered_bp\n"
        "app = func.FunctionApp()\n"
        "app.register_functions(registered_bp)\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == set()


def test_dfapp_register_blueprint_receiver_recognized_pass(tmp_path: Path) -> None:
    """A standard func.Blueprint() registered through a DFApp receiver's
    register_blueprint(...) must be recognized, not just FunctionApp (#446)."""
    handlers = import_module("azure_functions_doctor.handlers")
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\n"
        "import azure.durable_functions as df\n"
        "app = df.DFApp()\n"
        "bp = func.Blueprint()\n"
        "@bp.route(route='health')\n"
        "def health(req):\n"
        "    return req\n"
        "app.register_blueprint(bp)\n",
        encoding="utf-8",
    )

    assert handlers._collect_unregistered_blueprint_aliases(tmp_path) == set()
