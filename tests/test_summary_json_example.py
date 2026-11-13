"""Summary-JSON reporting example with stable counts (issue #667).

Gap audited: ``tests/test_bugfix_issues.py``, ``tests/test_skip_status.py`` and
``tests/test_gate_severity_independence.py`` assert the sidecar's keys, types and one
``gate_failed`` case, but no test or doc showed a user-facing reader that combines the counts
with doctor's exit status on a fixed project, and ``docs/configuration.md`` still listed the
sidecar without ``gate_failed``.
"""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest
from typer.testing import CliRunner

from azure_functions_doctor.cli import cli

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "examples" / "github-actions" / "read_doctor_summary.py"
DOC = ROOT / "docs" / "examples" / "ci_integration.md"

# Deterministic for ``--profile minimal``: six required, environment-independent rules.
EXPECTED = {
    "http-trigger": ({"passed": 6, "warned": 0, "failed": 0, "skipped": 0}, False, 0),
    "broken-missing-host-json": ({"passed": 4, "warned": 0, "failed": 2, "skipped": 0}, True, 1),
}

runner = CliRunner()


def _reader() -> ModuleType:
    spec = importlib.util.spec_from_file_location("read_doctor_summary", READER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(example: str, summary: Path, *extra: str) -> int:
    path = ROOT / "examples" / "v2" / example
    args = ["doctor", "--path", str(path), "--profile", "minimal", "--summary-json", str(summary)]
    return runner.invoke(cli, [*args, *extra]).exit_code


@pytest.mark.parametrize("example", sorted(EXPECTED))
def test_summary_counts_are_stable_and_match_exit_status(example: str, tmp_path: Path) -> None:
    counts, gate_failed, exit_code = EXPECTED[example]
    summary = tmp_path / "doctor-summary.json"
    assert _run(example, summary) == exit_code
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload == {**counts, "gate_failed": gate_failed}
    # The gate decision and the process exit status always agree.
    assert (exit_code == 1) is payload["gate_failed"]


@pytest.mark.parametrize("example", sorted(EXPECTED))
def test_counts_add_up_to_the_json_report_items(example: str, tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    report = tmp_path / "report.json"
    _run(example, summary, "--format", "json", "--output", str(report))
    payload = json.loads(summary.read_text(encoding="utf-8"))
    items = [
        i for s in json.loads(report.read_text(encoding="utf-8"))["results"] for i in s["items"]
    ]
    by_status = {
        status: sum(1 for i in items if i["status"] == status)
        for status in ("pass", "warn", "fail", "skip")
    }
    assert payload["passed"] == by_status["pass"]
    assert payload["warned"] == by_status["warn"]
    assert payload["failed"] == by_status["fail"]
    assert payload["skipped"] == by_status["skip"]
    assert sum(payload[k] for k in ("passed", "warned", "failed", "skipped")) == len(items)


@pytest.mark.parametrize("example", sorted(EXPECTED))
def test_reader_script_prints_counts_and_mirrors_the_gate(example: str, tmp_path: Path) -> None:
    counts, gate_failed, exit_code = EXPECTED[example]
    summary = tmp_path / "doctor-summary.json"
    _run(example, summary)
    done = subprocess.run([sys.executable, str(READER), str(summary)], capture_output=True)
    assert done.returncode == exit_code
    expected_line = (
        "doctor: "
        + " ".join(f"{k}={v}" for k, v in counts.items())
        + f" gate_failed={str(gate_failed).lower()}"
    )
    assert done.stdout.decode().strip() == expected_line


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"passed": 1, "warned": 0, "failed": 0, "skipped": 0}',
        '{"passed": "1", "warned": 0, "failed": 0, "skipped": 0, "gate_failed": false}',
        '{"passed": true, "warned": 0, "failed": 0, "skipped": 0, "gate_failed": false}',
        '{"passed": -1, "warned": 0, "failed": 0, "skipped": 0, "gate_failed": false}',
        '{"passed": 1, "warned": 0, "failed": 0, "skipped": 0, "gate_failed": "no"}',
        '{"passed": 1, "warned": 0, "failed": 0, "skipped": 0, "gate_failed": false, "x": 1}',
    ],
)
def test_reader_rejects_invalid_summaries(content: str, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(content, encoding="utf-8")
    done = subprocess.run([sys.executable, str(READER), str(bad)], capture_output=True)
    assert done.returncode == 2
    assert b"invalid doctor summary" in done.stderr
    with pytest.raises(ValueError):
        _reader().load_summary(bad)


def test_reader_rejects_missing_file_and_wrong_usage(tmp_path: Path) -> None:
    missing = subprocess.run(
        [sys.executable, str(READER), str(tmp_path / "nope.json")], capture_output=True
    )
    assert missing.returncode == 2
    usage = subprocess.run([sys.executable, str(READER)], capture_output=True)
    assert usage.returncode == 2


def test_docs_state_the_expected_counts_and_keys() -> None:
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## Summary counts with `--summary-json`")[1].split("\n## ")[0]
    flat = " ".join(section.split())
    for example, (counts, gate_failed, exit_code) in EXPECTED.items():
        assert f"examples/v2/{example}" in section or example == "http-trigger"
        expected = json.dumps({**counts, "gate_failed": gate_failed})
        assert expected in flat, expected
        assert f"exits `{exit_code}`" in flat
    for key in ("passed", "warned", "failed", "skipped", "gate_failed"):
        assert f"`{key}`" in section
    config = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert '"gate_failed": false}' in config
