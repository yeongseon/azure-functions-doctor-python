"""Guards that ``examples/README.md`` stays in sync with the checked-in fixtures (issue #660)."""

from pathlib import Path
import re

import pytest

from azure_functions_doctor.doctor import Doctor

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "examples" / "README.md"

# `| Name | `examples/v2/<dir>` | `<rule_id>` (warn|fail) ... |`
_ROW = re.compile(
    r"^\|[^|]+\|\s*`(?P<path>examples/v2/[\w-]+)`\s*\|\s*`(?P<rule>check_\w+)`\s*"
    r"\((?P<status>warn|fail)\)",
    re.MULTILINE,
)

_EXPECTED_FIXTURES = {
    "examples/v2/broken-dev-storage-leak": ("check_dev_storage_connection", "warn"),
    "examples/v2/broken-flex-deployment-storage": ("check_flex_deployment_storage", "warn"),
    "examples/v2/broken-flex-deprecated-settings": ("check_flex_deprecated_settings", "warn"),
    "examples/v2/broken-flex-runtime-config": ("check_flex_runtime_config", "fail"),
}


def _rows() -> dict[str, tuple[str, str]]:
    text = INDEX.read_text(encoding="utf-8")
    return {m["path"]: (m["rule"], m["status"]) for m in _ROW.finditer(text)}


def test_index_lists_every_flex_and_storage_fixture() -> None:
    rows = _rows()
    for path, expected in _EXPECTED_FIXTURES.items():
        assert rows.get(path) == expected, f"{path}: index row is missing or wrong"


def test_every_indexed_example_path_exists() -> None:
    text = INDEX.read_text(encoding="utf-8")
    paths = set(re.findall(r"`(examples/v2/[\w-]+)`", text))
    assert paths, "no example paths found in the index"
    for path in sorted(paths):
        assert (ROOT / path).is_dir(), f"{path} is listed in examples/README.md but missing"


def test_each_documented_fixture_has_a_run_command() -> None:
    text = INDEX.read_text(encoding="utf-8")
    for path in _EXPECTED_FIXTURES:
        assert f"azure-functions-doctor doctor --path {path}\n" in text, path


@pytest.mark.parametrize("path", sorted(_EXPECTED_FIXTURES))
def test_documented_status_matches_doctor_output(path: str) -> None:
    rule_id, status = _rows()[path]
    results = Doctor(str(ROOT / path)).run_all_checks()
    actual = {
        item["rule_id"]: item["status"]
        for section in results
        for item in section["items"]
        if "rule_id" in item
    }
    assert actual.get(rule_id) == status, f"{path}: {rule_id} is {actual.get(rule_id)!r}"
    # Other required rules stay quiet: only the documented rule may fail.
    failing = {rule for rule, state in actual.items() if state == "fail"}
    assert failing <= ({rule_id} if status == "fail" else set()), f"{path}: unexpected {failing}"
