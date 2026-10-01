from importlib import import_module
from pathlib import Path

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
loader.register_functions(other_bp)
loader.register_blueprint(flask_bp)
register_blueprint(flask_bare)
app.register_functions(factory())
"""
    assert handlers._collect_register_functions_args(source) == {"bp"}


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
    (tmp_path / "loader.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\napp.register_functions(bp)\n",
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


def test_blueprint_registration_fixture_passes_when_registered() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "blueprint_registered")
    assert item_map["Blueprint registration"] == "pass"


def test_blueprint_registration_fixture_warns_when_unregistered() -> None:
    item_map = _item_status_by_label(FIXTURES_DIR / "blueprint_unregistered")
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
