from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from tools.dependency_audit_policy import run_audit
from tools.security_report import Status


@pytest.mark.parametrize(
    "raw,code,status",
    [
        ('{"dependencies":[{"name":"example","version":"1","vulns":[]}]}', 0, Status.PASS),
        (
            '{"dependencies":[{"name":"example","version":"1","vulns":[{"id":"CVE-2026-12345","fix_versions":[]}]}]}',
            1,
            Status.FAIL,
        ),
        ('{"dependencies":[{"name":"example","skip_reason":"unavailable"}]}', 0, Status.INCOMPLETE),
    ],
)
def test_unpublished_candidate_audits_only_verified_dependencies(
    tmp_path: Path, raw: str, code: int, status: Status
) -> None:
    # Given a verified unpublished candidate and one installed dependency.
    for name, version in [("azure-functions-doctor", "9999.0"), ("example", "1")]:
        metadata = tmp_path / f"{name.replace('-', '_')}-{version}.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(f"Name: {name}\nVersion: {version}\n")
    policy = tmp_path / "policy.json"
    policy.write_text('{"schema_version":1,"blocking":"all-known-runtime","exceptions":[]}')
    inventories: list[str] = []

    def audit(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        inventories.append(Path(command[command.index("--requirement") + 1]).read_text())
        assert "--no-deps" in command and "--disable-pip" in command
        return subprocess.CompletedProcess(command, code, raw, "")

    # When auditing the isolated inventory, excluding only the identified first party.
    with (
        patch("subprocess.run", side_effect=audit),
        patch("tools.dependency_audit_policy.version", return_value="2.10.1"),
    ):
        result = run_audit(
            tmp_path, policy, candidate_name="azure-functions-doctor", candidate_version="9999.0"
        )
    # Then real advisories and third-party skips retain their blocking meanings.
    assert result.status == status
    assert inventories == ["example==1\n"]


def test_candidate_identity_mismatch_is_incomplete(tmp_path: Path) -> None:
    # Given an absent candidate; When audited; Then no service call can produce PASS.
    with patch("subprocess.run", side_effect=AssertionError("must not audit")):
        result = run_audit(
            tmp_path, tmp_path, candidate_name="azure-functions-doctor", candidate_version="9999.0"
        )
    assert result.status == Status.INCOMPLETE


def test_duplicate_installed_identity_is_incomplete(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate-1.dist-info"
    candidate.mkdir()
    (candidate / "METADATA").write_text("Name: candidate\nVersion: 1\n")
    for release in ("1", "2"):
        metadata = tmp_path / f"example-{release}.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(f"Name: example\nVersion: {release}\n")
    with patch("subprocess.run", side_effect=AssertionError("must not audit")):
        result = run_audit(tmp_path, tmp_path, candidate_name="candidate", candidate_version="1")
    assert result.status == Status.INCOMPLETE
