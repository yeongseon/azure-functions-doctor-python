"""Characterize scan isolation before deduplicating Python parsing."""

from pathlib import Path

from azure_functions_doctor.doctor import Doctor


def test_malformed_and_undecodable_sources_preserve_other_findings(tmp_path: Path) -> None:
    (tmp_path / "function_app.py").write_text(
        "import azure.functions as func\napp = func.FunctionApp()\n", encoding="utf-8"
    )
    (tmp_path / "broken.py").write_text("def broken(\n", encoding="utf-8")
    (tmp_path / "binary.py").write_bytes(b"\xff\xfe")
    doctor = Doctor(str(tmp_path), profile="full")

    first = doctor.run_all_checks()
    second = doctor.run_all_checks()

    assert first == second
    items = [item for section in first for item in section["items"]]
    assert any(item["status"] == "fail" for item in items)
    assert any(item["rule_id"] == "inspection_incomplete" for item in items)
    assert any(
        item["rule_id"] == "check_programming_model_v2" and item["status"] == "pass"
        for item in items
    )


def test_separate_scans_observe_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "function_app.py"
    source.write_text("import azure.functions as func\napp = func.FunctionApp()\n")
    first = Doctor(str(tmp_path), profile="minimal")
    source.write_text("class Unrelated: pass\n")

    second = Doctor(str(tmp_path), profile="minimal")

    assert first.programming_model == "v2"
    assert second.programming_model == "unknown"
