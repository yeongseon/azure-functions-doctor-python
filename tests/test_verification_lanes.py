from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from tools.verification import azure_preflight, execute, pytest_command, run_targets
from tools.verification_evidence import Summary, save
from tools.verification_wheel import main as wheel_smoke


def test_offline_selector_keeps_all_diagnostic_regression_modules() -> None:
    command = pytest_command("test", [])
    assert "tests/" in command
    assert [arg for arg in command if arg.startswith("--ignore")] == [
        "--ignore=tests/e2e",
        "--ignore=tests/host_smoke",
    ]
    assert command[command.index("-m", 3) + 1] == "not e2e"


def test_host_missing_tools_records_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification.doctor", lambda live: 1)
    assert execute("host-smoke", []) != 0
    assert (
        json.loads(Path("test-results/host-smoke/summary.json").read_text())["status"]
        == "INCOMPLETE"
    )


def test_verify_runs_every_lane_after_failure_and_rejects_stale_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def failing_run(command: list[str], log: Path, timeout: float = 600) -> int:
        calls.append(command[1])
        return 1

    monkeypatch.chdir(tmp_path)
    save(Path("test-results/test"), Summary(1, "test", ("old",), 1, 1, 0, 0, "PASS", 0))
    monkeypatch.setattr("tools.verification.run", failing_run)
    targets = ("check", "test", "integration", "wheel-smoke", "build", "docs")
    assert run_targets("verify", targets) != 0
    assert calls == list(targets)
    lanes = json.loads(Path("test-results/verify/lanes.json").read_text())
    assert lanes[1]["status"] == "INCOMPLETE"


def test_integration_reports_workflow_only_lanes_not_applicable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def passing_run(command: list[str], log: Path, timeout: float = 600) -> int:
        lane = command[1]
        save(Path("test-results") / lane, Summary(1, lane, ("test",), 1, 1, 0, 0, "PASS", 0))
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification.run", passing_run)
    assert run_targets("integration", ("cli-smoke", "host-smoke")) == 0
    lanes = json.loads(Path("test-results/integration/lanes.json").read_text())
    assert [lane["status"] for lane in lanes] == ["PASS", "PASS"] + ["NOT_APPLICABLE"] * 3


def test_azure_candidate_version_mismatch_blocks_before_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("E2E_BASE_URL", "https://candidate.azurewebsites.net")
    monkeypatch.setenv("E2E_EXPECTED_VERSION", "999.0.0")
    assert "differs" in azure_preflight()


def test_wheel_smoke_rejects_stale_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/stale.whl").write_bytes(b"stale")

    def empty_build(command: list[str], log: Path, timeout: float = 600) -> int:
        assert "--outdir" in command
        assert str(tmp_path / "dist") not in command
        return 0

    monkeypatch.delenv("VERIFICATION_WHEEL", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification_wheel.run", empty_build)
    assert wheel_smoke() != 0


def test_wheel_smoke_installs_candidate_when_parent_has_same_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a candidate and a dependency environment containing the same version.
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"candidate")
    monkeypatch.setenv("VERIFICATION_WHEEL", str(wheel))
    monkeypatch.chdir(tmp_path)
    installed = False

    def candidate_run(
        command: list[str], log: Path, timeout: float = 600, *, cwd: Path | None = None
    ) -> int:
        nonlocal installed
        if "venv" in command:
            packages = (
                Path(command[-1])
                / "lib"
                / f"python{sys.version_info.major}.{sys.version_info.minor}"
                / "site-packages"
            )
            packages.mkdir(parents=True)
        elif "pip" in command:
            # Pip otherwise skips the wheel visible through the dependency .pth.
            assert "--force-reinstall" in command
            assert "--no-deps" in command and "--no-index" in command
            installed = True
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("{}")
        return 0

    monkeypatch.setattr("tools.verification_wheel.run", candidate_run)
    # When wheel smoke installs into its private environment.
    result = wheel_smoke()
    # Then the same-version candidate is actually installed, not silently skipped.
    assert result == 0
    assert installed
