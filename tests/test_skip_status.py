"""Tests for the explicit ``skip`` diagnostic status (issue #286).

Previously handlers that could not run a check (missing prerequisite, feature
not used, file absent) reported ``pass``, so a *skipped* check was
indistinguishable from a *verified-healthy* one. These tests lock in the new
``skip`` status across the output contract: styling, the canonical mapping in
``Doctor.run_all_checks``, JSON summary counts, JUnit, SARIF, exit codes, and
the human-readable table.
"""

import json
from pathlib import Path
from typing import Any, cast
import xml.etree.ElementTree as ET

from typer.testing import CliRunner

from azure_functions_doctor.cli import cli as app
from azure_functions_doctor.handlers._helpers import Rule
from azure_functions_doctor.handlers.registry import HandlerRegistry
from azure_functions_doctor.utils import (
    DETAIL_COLOR_MAP,
    STATUS_ICONS,
    STATUS_STYLES,
    format_status_icon,
)

runner = CliRunner()

# A valid v2 project that exercises several skip-producing handlers
# (no Durable Functions, no local.settings.json, etc.).
V2_FIXTURE_PATH = "examples/v2/http-trigger"


def _json_status_counts(path: str) -> dict[str, int]:
    result = runner.invoke(app, ["doctor", "--path", path, "--format", "json"])
    data = json.loads(result.output)
    counts: dict[str, int] = {}
    for section in data["results"]:
        for item in section["items"]:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# utils: skip is a first-class status
# ---------------------------------------------------------------------------


def test_skip_registered_in_status_maps() -> None:
    assert STATUS_ICONS.get("skip") == "–"
    assert "skip" in STATUS_STYLES
    assert DETAIL_COLOR_MAP.get("skip") == "bright_black"


def test_format_status_icon_skip() -> None:
    assert format_status_icon("skip") == "–"


# ---------------------------------------------------------------------------
# handler layer: prerequisite-absent handlers return skip (not pass)
# ---------------------------------------------------------------------------


def test_durable_handler_returns_skip_when_not_used(tmp_path: Path) -> None:
    registry = HandlerRegistry()
    rule = cast(
        Rule,
        {"type": "conditional_exists", "required": False, "condition": {}},
    )
    result = registry.handle(rule, tmp_path)
    assert result["status"] == "skip"


# ---------------------------------------------------------------------------
# doctor transform + JSON: skip is preserved and never fails a section
# ---------------------------------------------------------------------------


def test_v2_project_reports_skip_items_and_exits_zero() -> None:
    result = runner.invoke(app, ["doctor", "--path", V2_FIXTURE_PATH, "--format", "json"])
    assert result.exit_code == 0
    counts = _json_status_counts(V2_FIXTURE_PATH)
    assert counts.get("skip", 0) > 0
    # skip must not be silently folded into pass/warn/fail.
    assert set(counts).issuperset({"pass", "skip"})


# ---------------------------------------------------------------------------
# summary JSON sidecar exposes the skipped count
# ---------------------------------------------------------------------------


def test_summary_json_includes_skipped_count(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    result = runner.invoke(
        app,
        [
            "doctor",
            "--path",
            V2_FIXTURE_PATH,
            "--summary-json",
            str(summary_path),
        ],
    )
    assert result.exit_code in (0, 1)
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"passed", "warned", "failed", "skipped", "gate_failed"}
    counts = _json_status_counts(V2_FIXTURE_PATH)
    assert payload["skipped"] == counts.get("skip", 0)


# ---------------------------------------------------------------------------
# JUnit: skipped checks map to <skipped>, never <failure>
# ---------------------------------------------------------------------------


def test_junit_skip_items_emit_skipped_element() -> None:
    result = runner.invoke(app, ["doctor", "--path", V2_FIXTURE_PATH, "--format", "junit"])
    root = ET.fromstring(result.output)  # noqa: S314 - trusted local output
    assert root.tag == "testsuite"
    counts = _json_status_counts(V2_FIXTURE_PATH)
    expected_skipped = counts.get("skip", 0) + counts.get("warn", 0)
    assert int(root.attrib.get("skipped", "0")) == expected_skipped
    # No skip item may be rendered as a failure.
    for case in root.findall("testcase"):
        assert not (case.findall("failure") and case.findall("skipped"))


# ---------------------------------------------------------------------------
# SARIF: skipped checks are not findings and must be excluded
# ---------------------------------------------------------------------------


def test_sarif_excludes_skipped_checks() -> None:
    result = runner.invoke(app, ["doctor", "--path", V2_FIXTURE_PATH, "--format", "sarif"])
    sarif = json.loads(result.output)
    sarif_results: list[dict[str, Any]] = sarif["runs"][0]["results"]
    counts = _json_status_counts(V2_FIXTURE_PATH)
    # Only fail + warn are findings; pass and skip are excluded.
    assert len(sarif_results) == counts.get("fail", 0) + counts.get("warn", 0)
    levels = {r["level"] for r in sarif_results}
    assert "none" not in levels  # skips are omitted, not emitted as level "none"


# ---------------------------------------------------------------------------
# table output surfaces the skip status to the user
# ---------------------------------------------------------------------------


def test_table_output_renders_skip_status() -> None:
    result = runner.invoke(app, ["doctor", "--path", V2_FIXTURE_PATH, "--format", "table"])
    assert "(skip)" in result.output
