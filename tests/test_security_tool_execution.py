from importlib.metadata import PackageNotFoundError
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from tools import dependency_audit_policy, security_evidence
from tools.security_report import Status


@pytest.mark.parametrize("failure", [OSError(), subprocess.TimeoutExpired("scanner", 1)])
def test_tool_failures_discard_raw_diagnostics(tmp_path: Path, failure: Exception) -> None:
    # Given unavailable scanners; When invoked; Then failure never becomes PASS.
    (tmp_path / "example.dist-info").mkdir()
    with patch("subprocess.run", side_effect=failure):
        assert security_evidence.run_bandit().status == Status.TOOL_ERROR
        assert dependency_audit_policy.run_audit(tmp_path, tmp_path).status == Status.TOOL_ERROR


def test_inventory_mismatch_is_incomplete_when_scanner_omits_file() -> None:
    # Given scanner evidence omitting one actual product file.
    metrics = {
        p.as_posix(): {"loc": 1}
        for surface in security_evidence.SCOPE
        for p in Path(surface).rglob("*.py")
    }
    del metrics[next(iter(metrics))]
    metrics["_totals"] = {"loc": len(metrics)}
    raw = json.dumps({"errors": [], "metrics": metrics, "results": []})
    with (
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                [], 0, stdout=raw, stderr="CANARY_SECRET_STDERR"
            ),
        ),
        patch.object(security_evidence, "version", return_value="1.9.4"),
    ):
        # When the helper compares actual and reported inventory.
        result = security_evidence.run_bandit()
    # Then missing scope cannot masquerade as a clean scan.
    assert result.status == Status.INCOMPLETE
    assert "CANARY_SECRET" not in repr(result)


def test_missing_bandit_metadata_is_tool_error() -> None:
    # Given valid scanner output but unavailable tool identity metadata.
    metrics = {
        p.as_posix(): {"loc": 1}
        for surface in security_evidence.SCOPE
        for p in Path(surface).rglob("*.py")
    }
    metrics["_totals"] = {"loc": len(metrics)}
    raw = json.dumps({"errors": [], "metrics": metrics, "results": []})
    with (
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout=raw, stderr=""),
        ),
        patch.object(security_evidence, "version", side_effect=PackageNotFoundError("bandit")),
    ):
        # When evidence collection cannot identify the scanner.
        result = security_evidence.run_bandit()
    # Then missing tooling still fails closed, even with clean scanner output.
    assert result.status == Status.TOOL_ERROR


def test_audit_reads_only_isolated_installation(tmp_path: Path) -> None:
    # Given one isolated wheel installation and an empty runtime exception policy.
    (tmp_path / "example.dist-info").mkdir()
    policy = tmp_path / "policy.json"
    policy.write_text('{"schema_version":1,"blocking":"all-known-runtime","exceptions":[]}')
    raw = '{"dependencies":[{"name":"example","version":"1","vulns":[]}]}'
    with (
        patch(
            "subprocess.run",
            return_value=subprocess.CompletedProcess(
                [], 0, stdout=raw, stderr="CANARY_SECRET_STDERR"
            ),
        ) as run,
        patch.object(dependency_audit_policy, "version", return_value="2.10.1"),
    ):
        # When the runtime installation is audited.
        result = dependency_audit_policy.run_audit(tmp_path, policy)
    # Then tooling packages cannot contaminate that closure.
    command = run.call_args.args[0]
    assert command[command.index("--path") + 1] == str(tmp_path)
    assert run.call_args.kwargs["timeout"] == 300
    assert result.status == Status.PASS
    assert "CANARY_SECRET" not in repr(result)
