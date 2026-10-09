from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci-test.yml"


def run_gate(results: dict[str, str], *, full: str, docs: str) -> subprocess.CompletedProcess[str]:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"python3 - <<'EVAL'\n(?P<script>.*?)\n          EVAL", workflow, re.DOTALL)
    assert match is not None
    script = "\n".join(
        line.removeprefix("          ") for line in match.group("script").splitlines()
    )
    env = os.environ | {
        "RESULTS": json.dumps({job: {"result": result} for job, result in results.items()}),
        "FULL_REQUIRED": full,
        "DOCS_CHANGED": docs,
    }
    return subprocess.run(
        ["python3", "-c", script],
        capture_output=True,
        env=env,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("full,docs", [("", "true"), ("yes", "true"), ("true", ""), ("true", "no")])
def test_gate_rejects_missing_or_invalid_classifier_outputs(full: str, docs: str) -> None:
    result = run_gate({"changes": "success"}, full=full, docs=docs)
    assert result.returncode != 0


def test_gate_rejects_impossible_skip_everything_output() -> None:
    result = run_gate({"changes": "success"}, full="false", docs="false")
    assert result.returncode != 0


@pytest.mark.parametrize("result", ["failure", "skipped"])
def test_gate_requires_unknown_jobs_to_succeed(result: str) -> None:
    gate = run_gate(
        {"changes": "success", "docs-check": "success", "future-job": result},
        full="false",
        docs="true",
    )
    assert gate.returncode != 0


def test_gate_rejects_classifier_success_without_outputs() -> None:
    result = run_gate({"changes": "success"}, full="", docs="")
    assert result.returncode != 0
