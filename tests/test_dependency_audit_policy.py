from datetime import date
import json

import pytest

from tools.dependency_audit_policy import classify_audit
from tools.security_exceptions import parse_exceptions
from tools.security_report import EvidenceError, Status, load

TODAY = date(2026, 10, 23)
POLICY = '{"schema_version":1,"blocking":"all-known-runtime","exceptions":[]}'


def payload(vulnerable: bool = False) -> str:
    return json.dumps(
        {
            "dependencies": [
                {
                    "name": "example",
                    "version": "1",
                    "vulns": [
                        {"id": "CVE-2026-12345", "fix_versions": [], "description": "CANARY_SECRET"}
                    ]
                    if vulnerable
                    else [],
                }
            ]
        }
    )


@pytest.mark.parametrize("vulnerable,status", [(False, Status.PASS), (True, Status.FAIL)])
def test_known_advisories_block_when_severity_unknown(vulnerable: bool, status: Status) -> None:
    # Given runtime packages; When classified; Then unexcepted advisories block.
    result = classify_audit(payload(vulnerable), int(vulnerable), policy_raw=POLICY, today=TODAY)
    assert result.status == status
    assert "CANARY_SECRET" not in repr(result)


@pytest.mark.parametrize("raw", ["", "invalid", "{}"])
def test_invalid_output_is_tool_error(raw: str) -> None:
    # Given missing evidence; When classified; Then it cannot pass.
    assert classify_audit(raw, 0, policy_raw=POLICY, today=TODAY).status == Status.TOOL_ERROR


@pytest.mark.parametrize("raw", ['{"dependencies":[]}', '{"dependencies":[{"skip_reason":"x"}]}'])
def test_empty_or_skipped_scope_is_incomplete(raw: str) -> None:
    # Given unscanned dependencies; When classified; Then completeness blocks.
    assert classify_audit(raw, 0, policy_raw=POLICY, today=TODAY).status == Status.INCOMPLETE


def exception_policy() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "blocking": "all-known-runtime",
            "exceptions": [
                {
                    "id": "CVE-2026-12345",
                    "package": "example",
                    "kind": "fix-not-available",
                    "reason": "no patched release",
                    "owner": "maintainer",
                    "added": "2026-10-01",
                    "expires": "2026-11-01",
                }
            ],
        }
    )


def test_exception_expires_and_stops_applying_when_fix_exists() -> None:
    # Given an owned no-fix exception; When expired or fixed; Then it no longer waives.
    policy = exception_policy()
    assert classify_audit(payload(True), 1, policy_raw=policy, today=TODAY).status == Status.PASS
    raw = payload(True).replace('"fix_versions": []', '"fix_versions": ["2"]')
    assert classify_audit(raw, 1, policy_raw=policy, today=TODAY).status == Status.FAIL
    assert (
        classify_audit(payload(True), 1, policy_raw=policy, today=date(2026, 11, 2)).status
        == Status.FAIL
    )


@pytest.mark.parametrize("field", ["owner", "reason", "added", "expires"])
def test_exception_requires_owned_reason_and_expiry(field: str) -> None:
    # Given a missing required field; When evaluated; Then policy fails closed.
    policy = json.loads(exception_policy())
    del policy["exceptions"][0][field]
    assert (
        classify_audit(payload(True), 1, policy_raw=json.dumps(policy), today=TODAY).status
        == Status.TOOL_ERROR
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"expires": "2027-10-23"},
        {"added": "2026-11-01"},
        {"kind": "ignore-all"},
        {"line": -1},
        {"line": True},
        {"owner": ""},
        {"reason": ""},
    ],
)
def test_invalid_exceptions_are_rejected(patch: dict[str, str | int]) -> None:
    # Given invalid exception metadata; When parsed; Then it cannot waive findings.
    policy = json.loads(exception_policy())
    policy["exceptions"][0].update(patch)
    with pytest.raises((EvidenceError, ValueError)):
        parse_exceptions(load(json.dumps(policy))["exceptions"], TODAY)


@pytest.mark.parametrize("code", [0, 2])
def test_exit_status_must_agree_with_findings(code: int) -> None:
    # Given inconsistent status; When classified; Then evidence is unusable.
    assert (
        classify_audit(payload(True), code, policy_raw=POLICY, today=TODAY).status
        == Status.TOOL_ERROR
    )
