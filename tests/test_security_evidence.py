from datetime import date
import json
from pathlib import Path

import pytest

from tools.security_evidence import apply_bandit_policy, classify_bandit, semgrep_evidence
from tools.security_report import Check, Status, write_report


def payload() -> str:
    return json.dumps(
        {"errors": [], "metrics": {"_totals": {"loc": 10}, "src/x.py": {"loc": 10}}, "results": []}
    )


@pytest.mark.parametrize(
    "raw,code,status",
    [
        ("", 2, Status.TOOL_ERROR),
        ("invalid", 0, Status.TOOL_ERROR),
        ('{"errors":[],"metrics":{"_totals":{}},"results":[]}', 0, Status.INCOMPLETE),
    ],
)
def test_missing_evidence_fails_closed(raw: str, code: int, status: Status) -> None:
    # Given missing evidence; When classified; Then it cannot pass.
    assert classify_bandit(raw, code, floor=1).status == status


def test_complete_scan_has_real_counts() -> None:
    # Given a scanned file; When classified; Then its inventory is reported.
    result = classify_bandit(payload(), 0, floor=1)
    assert result.status == Status.PASS
    assert result.counts == {"files": 1, "loc": 10, "errors": 0}


@pytest.mark.parametrize("severity", ["LOW", "MEDIUM", "HIGH"])
def test_findings_block_without_exporting_payload(severity: str, tmp_path: Path) -> None:
    # Given secret-bearing diagnostics; When rendered; Then metadata alone survives.
    data = json.loads(payload())
    data["results"] = [
        {
            "test_id": "B105",
            "filename": "src/x.py",
            "line_number": 3,
            "issue_severity": severity,
            "issue_confidence": "HIGH",
            "code": "Bearer CANARY_SECRET",
            "issue_text": "AccountKey=CANARY_SECRET",
        }
    ]
    result = classify_bandit(json.dumps(data), 1, floor=1)
    summary = tmp_path / "summary.md"
    assert write_report([result], tmp_path, summary) == 1
    assert "CANARY_SECRET" not in (tmp_path / "summary.json").read_text() + summary.read_text()
    assert result.counts[f"severity.{severity}"] == 1


@pytest.mark.parametrize("field", ["nosec", "skipped_tests"])
def test_scanner_skips_fail_completeness(field: str) -> None:
    # Given scanner skips; When classified; Then completeness fails.
    data = json.loads(payload())
    data["metrics"]["_totals"][field] = 1
    assert classify_bandit(json.dumps(data), 0, floor=1).status == Status.INCOMPLETE


def test_static_exception_requires_exact_location_and_current_expiry() -> None:
    # Given a reviewed exception; When location/expiry changes; Then it cannot waive findings.
    data = json.loads(payload())
    data["results"] = [
        {
            "test_id": "B404",
            "filename": "src/x.py",
            "line_number": 1,
            "issue_severity": "LOW",
            "issue_confidence": "HIGH",
        }
    ]
    check = classify_bandit(json.dumps(data), 1, floor=1)
    rule = {
        "id": "B404",
        "file": "src/x.py",
        "line": 1,
        "kind": "reviewed-static",
        "reason": "fixed shell-free command",
        "owner": "maintainer",
        "added": "2026-10-01",
        "expires": "2026-11-01",
    }
    policy = json.dumps({"schema_version": 1, "exceptions": [rule]})
    assert apply_bandit_policy(check, policy, date(2026, 10, 23)).status == Status.PASS
    assert apply_bandit_policy(check, policy, date(2026, 11, 2)).status == Status.FAIL
    rule["line"] = 2
    assert (
        apply_bandit_policy(
            check, json.dumps({"schema_version": 1, "exceptions": [rule]}), date(2026, 10, 23)
        ).status
        == Status.FAIL
    )


@pytest.mark.parametrize(
    "outcome,status",
    [
        ("success", Status.PASS),
        ("failure", Status.TOOL_ERROR),
        ("skipped", Status.INCOMPLETE),
    ],
)
def test_semgrep_counts_remain_unknown(outcome: str, status: Status) -> None:
    # Given an action outcome; When recorded; Then counts are not invented.
    check = semgrep_evidence(outcome)
    assert check.status == status
    assert check.counts == {}


@pytest.mark.parametrize(
    "status,code",
    [
        (Status.PASS, 0),
        (Status.FAIL, 1),
        (Status.TOOL_ERROR, 2),
        (Status.INCOMPLETE, 3),
    ],
)
def test_status_exit_codes_are_distinct(status: Status, code: int) -> None:
    # Given a classified status; When returned; Then CI can distinguish failures.
    assert Check("test", (), status, 0).returncode == code
