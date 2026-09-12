"""Tests for config-based rule suppression and path exclusion (issue #290)."""

from pathlib import Path
import shutil
from typing import Iterator, Optional

import pytest

from azure_functions_doctor.doctor import CheckResult, Doctor, SectionResult
from azure_functions_doctor.handlers._helpers import (
    _is_excluded_path,
    _iter_project_py_contents,
    _matches_extra_exclude,
    load_doctor_config,
    reset_extra_excludes,
    set_extra_excludes,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "v2" / "http-trigger"


def _write_config(root: Path, body: str) -> None:
    (root / "pyproject.toml").write_text(body, encoding="utf-8")


def _copy_example(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    shutil.copytree(EXAMPLE, project)
    return project


class TestLoadDoctorConfig:
    def test_reads_ignore_and_exclude(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            "[tool.azure-functions-doctor]\n"
            'ignore = ["check_python_version", "check_host_json"]\n'
            'exclude = ["legacy", "vendor/*.py"]\n',
        )
        config = load_doctor_config(tmp_path)
        assert config["ignore"] == ["check_python_version", "check_host_json"]
        assert config["exclude"] == ["legacy", "vendor/*.py"]

    def test_missing_pyproject_returns_empty(self, tmp_path: Path) -> None:
        assert load_doctor_config(tmp_path) == {"ignore": [], "exclude": []}

    def test_missing_table_returns_empty(self, tmp_path: Path) -> None:
        _write_config(tmp_path, '[project]\nname = "demo"\n')
        assert load_doctor_config(tmp_path) == {"ignore": [], "exclude": []}

    def test_non_table_tool_returns_empty(self, tmp_path: Path) -> None:
        _write_config(tmp_path, 'tool = "not-a-table"\n')
        assert load_doctor_config(tmp_path) == {"ignore": [], "exclude": []}

    def test_non_list_values_are_ignored(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            '[tool.azure-functions-doctor]\nignore = "check_python_version"\nexclude = 42\n',
        )
        assert load_doctor_config(tmp_path) == {"ignore": [], "exclude": []}

    def test_non_string_list_entries_are_dropped(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            '[tool.azure-functions-doctor]\nignore = ["check_python_version", 123, true]\n',
        )
        assert load_doctor_config(tmp_path) == {
            "ignore": ["check_python_version"],
            "exclude": [],
        }


class TestExtraExcludes:
    @pytest.fixture(autouse=True)
    def _clear(self) -> Iterator[None]:
        token = set_extra_excludes(Path(), ())
        yield
        reset_extra_excludes(token)

    def test_no_globs_matches_nothing(self, tmp_path: Path) -> None:
        assert _matches_extra_exclude(tmp_path / "legacy" / "a.py") is False

    def test_file_glob_matches(self, tmp_path: Path) -> None:
        # fnmatch ``*`` spans path separators, so a file glob also excludes
        # matching files deeper in the subtree (errs toward excluding more).
        token = set_extra_excludes(tmp_path, ["vendor/*.py"])
        try:
            assert _is_excluded_path(tmp_path / "vendor" / "x.py") is True
            assert _is_excluded_path(tmp_path / "vendor" / "sub" / "x.py") is True
            assert _is_excluded_path(tmp_path / "vendor" / "x.txt") is False
        finally:
            reset_extra_excludes(token)

    def test_directory_glob_matches_tree(self, tmp_path: Path) -> None:
        token = set_extra_excludes(tmp_path, ["legacy/"])
        try:
            assert _matches_extra_exclude(tmp_path / "legacy") is True
            assert _matches_extra_exclude(tmp_path / "legacy" / "deep" / "a.py") is True
            assert _matches_extra_exclude(tmp_path / "src" / "a.py") is False
        finally:
            reset_extra_excludes(token)

    def test_blank_glob_entry_is_skipped(self, tmp_path: Path) -> None:
        token = set_extra_excludes(tmp_path, ["   "])
        try:
            assert _matches_extra_exclude(tmp_path / "any.py") is False
        finally:
            reset_extra_excludes(token)

    def test_path_outside_root_is_not_matched(self, tmp_path: Path) -> None:
        token = set_extra_excludes(tmp_path / "root", ["*"])
        try:
            assert _matches_extra_exclude(tmp_path / "other" / "a.py") is False
        finally:
            reset_extra_excludes(token)

    def test_excluded_dir_still_wins_without_globs(self, tmp_path: Path) -> None:
        assert _is_excluded_path(tmp_path / ".venv" / "lib" / "a.py") is True

    def test_iter_py_contents_respects_extra_globs(self, tmp_path: Path) -> None:
        (tmp_path / "keep.py").write_text("x = 1\n", encoding="utf-8")
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "old.py").write_text("y = 2\n", encoding="utf-8")

        token = set_extra_excludes(tmp_path, ["legacy"])
        try:
            names = {p.name for p, _ in _iter_project_py_contents(tmp_path)}
        finally:
            reset_extra_excludes(token)
        assert "keep.py" in names
        assert "old.py" not in names


class TestDoctorIntegration:
    def test_ignored_rule_reported_as_skip(self, tmp_path: Path) -> None:
        project = _copy_example(tmp_path)
        _write_config(
            project,
            '[tool.azure-functions-doctor]\nignore = ["check_python_version"]\n',
        )
        doctor = Doctor(str(project))
        assert doctor.ignore_rules == {"check_python_version"}
        results = doctor.run_all_checks()
        item = _find_item(results, "check_python_version")
        assert item is not None
        assert item["status"] == "skip"
        assert "Suppressed by pyproject" in item["value"]

    def test_no_config_runs_rule_normally(self, tmp_path: Path) -> None:
        project = _copy_example(tmp_path)
        doctor = Doctor(str(project))
        assert doctor.ignore_rules == set()
        results = doctor.run_all_checks()
        item = _find_item(results, "check_python_version")
        assert item is not None
        assert item["status"] != "skip"

    def test_exclude_globs_loaded_into_doctor(self, tmp_path: Path) -> None:
        project = _copy_example(tmp_path)
        _write_config(
            project,
            '[tool.azure-functions-doctor]\nexclude = ["legacy", "vendor/*.py"]\n',
        )
        doctor = Doctor(str(project))
        assert doctor.exclude_globs == ["legacy", "vendor/*.py"]

    def test_cli_profile_still_applies_with_config(self, tmp_path: Path) -> None:
        # Precedence: the CLI-selected profile governs ruleset selection; config
        # ``ignore`` layers on top by turning a surviving rule into a skip.
        project = _copy_example(tmp_path)
        _write_config(
            project,
            '[tool.azure-functions-doctor]\nignore = ["check_python_version"]\n',
        )
        doctor = Doctor(str(project), profile="minimal")
        results = doctor.run_all_checks()
        item = _find_item(results, "check_python_version")
        # check_python_version is a required rule, so it survives the minimal
        # profile and is then suppressed to skip by the config ignore.
        assert item is not None
        assert item["status"] == "skip"


def _find_item(results: list[SectionResult], rule_id: str) -> Optional[CheckResult]:
    for section in results:
        for item in section["items"]:
            if item["rule_id"] == rule_id:
                return item
    return None
