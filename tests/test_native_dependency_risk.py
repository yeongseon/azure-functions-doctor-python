# pyright: reportMissingImports=false

from pathlib import Path

from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.handlers import (
    Rule,
    _detect_native_dependency_risks,
    generic_handler,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "v2"


def test_detect_native_dependency_risks_empty_requirements() -> None:
    assert _detect_native_dependency_risks("") == []


def test_detect_native_dependency_risks_pure_python_only() -> None:
    requirements = "azure-functions\nrequests==2.32.3\n"
    assert _detect_native_dependency_risks(requirements) == []


def test_detect_native_dependency_risks_mixed_packages() -> None:
    requirements = "azure-functions\npyodbc==5.0.0\npillow>=10\nrequests\n"
    matches = _detect_native_dependency_risks(requirements)
    assert [package for package, _hint in matches] == ["pyodbc", "pillow"]


def test_detect_native_dependency_risks_handles_comments_and_extras() -> None:
    requirements = (
        "# cryptography should be ignored in comments\n"
        "azure-functions\n"
        "cryptography[ssh]==44.0.0\n"
        "orjson==3.10.0  # inline comment\n"
    )
    matches = _detect_native_dependency_risks(requirements)
    assert [package for package, _hint in matches] == ["cryptography", "orjson"]


def test_native_dependency_risk_handler_skips_missing_requirements(tmp_path: Path) -> None:
    rule: Rule = {"type": "native_dependency_risk", "condition": {"file": "requirements.txt"}}
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "skip"


def test_native_dependency_risk_handler_passes_for_pure_python_requirements(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("azure-functions\nrequests==2.32.3\n", encoding="utf-8")
    rule: Rule = {"type": "native_dependency_risk", "condition": {"file": "requirements.txt"}}
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "pass"
    assert "No native dependency risk packages declared" in result["detail"]


def test_native_dependency_risk_handler_reports_matches_and_hints(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("azure-functions\npyodbc==5.0.0\npsycopg2==2.9.9\n", encoding="utf-8")
    rule: Rule = {"type": "native_dependency_risk", "condition": {"file": "requirements.txt"}}
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "fail"
    assert "Native dependencies detected: pyodbc, psycopg2" in result["detail"]
    assert "remote build" in result["detail"]
    assert "psycopg2-binary" in result["detail"]


def test_native_dependency_risk_handler_detects_included_requirements(tmp_path: Path) -> None:
    """A native-risk package declared only in a local -r/--requirement
    include must still be detected -- moving the same declaration into an
    included file must not make the check report a clean result (#587)."""
    (tmp_path / "requirements.txt").write_text("-r base.txt\n", encoding="utf-8")
    (tmp_path / "base.txt").write_text("azure-functions==1.25.0\nnumpy\n", encoding="utf-8")
    rule: Rule = {"type": "native_dependency_risk", "condition": {"file": "requirements.txt"}}
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "fail"
    assert "numpy" in result["detail"]


def test_native_dependency_risk_handler_safe_requirements_via_requirement_flag(
    tmp_path: Path,
) -> None:
    """The long-form --requirement flag is followed the same way as -r,
    and a safe (non-native) included declaration still passes (#587)."""
    (tmp_path / "requirements.txt").write_text("--requirement base.txt\n", encoding="utf-8")
    (tmp_path / "base.txt").write_text(
        "azure-functions==1.25.0\npackaging==25.0\n", encoding="utf-8"
    )
    rule: Rule = {"type": "native_dependency_risk", "condition": {"file": "requirements.txt"}}
    result = generic_handler(rule, tmp_path)
    assert result["status"] == "pass"


def test_native_dependency_risk_fixture_warns_in_full_profile() -> None:
    doctor = Doctor(str(FIXTURES_DIR / "native_deps_present"), profile="full")
    results = doctor.run_all_checks()
    item_map = {item["label"]: item for section in results for item in section["items"]}

    assert item_map["Native dependency risk"]["status"] == "warn"
    assert "pyodbc" in item_map["Native dependency risk"]["value"]


def test_native_dependency_risk_fixture_passes_for_pure_python_project() -> None:
    doctor = Doctor(str(FIXTURES_DIR / "pure_python_only"), profile="full")
    results = doctor.run_all_checks()
    item_map = {item["label"]: item for section in results for item in section["items"]}

    assert item_map["Native dependency risk"]["status"] == "pass"


def test_native_dependency_risk_rule_filtered_from_minimal_profile() -> None:
    doctor = Doctor(str(FIXTURES_DIR / "native_deps_present"), profile="minimal")
    results = doctor.run_all_checks()
    item_labels = {item["label"] for section in results for item in section["items"]}

    assert "Native dependency risk" not in item_labels
