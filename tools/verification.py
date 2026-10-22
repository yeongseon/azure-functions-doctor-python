"""Canonical local/CI lane runner; Azure certification remains a separate scope."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from importlib.metadata import version
import ipaddress
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from tools.verification_environment import clean, doctor
from tools.verification_evidence import Status, Summary, collect, publish, redact, report, save
from tools.verification_host import host_smoke
from tools.verification_process import run


def fresh(directory: Path) -> None:
    if directory.exists():
        shutil.rmtree(directory)
    (directory / "logs").mkdir(parents=True)


def pytest_command(lane: str, extra: list[str]) -> list[str]:
    directory = Path("test-results") / lane
    command = [sys.executable, "-m", "pytest"]
    if lane == "test":
        command += [
            "tests/",
            "-m",
            "not e2e",
            "--ignore=tests/e2e",
            "--ignore=tests/host_smoke",
            "--cov-report=xml:" + str(directory / "coverage.xml"),
        ]
    else:
        command += ["tests/e2e/", "-m", "e2e", "--no-cov"]
    return [*command, *extra, "--junitxml=" + str(directory / "junit.xml")]


def azure_preflight(local: bool = False) -> str:
    try:
        url = urlsplit(os.environ.get("E2E_BASE_URL", ""))
        host = url.hostname or ""
        port = url.port
        if not host or url.username or url.password or url.fragment:
            return "E2E_BASE_URL must be a valid deployed HTTPS URL without credentials"
        if not local:
            if url.scheme != "https" or host == "localhost" or host.endswith(".localhost"):
                return "E2E_BASE_URL must identify a deployed HTTPS host, not localhost"
            try:
                if not ipaddress.ip_address(host).is_global:
                    return "E2E_BASE_URL must not identify a private or loopback address"
            except ValueError:
                if "." not in host:
                    return "E2E_BASE_URL requires a deployed hostname"
        elif url.scheme not in {"http", "https"}:
            return "Local E2E requires an HTTP URL"
        if port == 0:
            return "E2E_BASE_URL has an invalid port"
    except ValueError:
        return "E2E_BASE_URL is invalid"
    expected = os.environ.get("E2E_EXPECTED_VERSION", "")
    if not expected:
        return "E2E_EXPECTED_VERSION is required for candidate identity"
    if expected != version("azure-functions-doctor"):
        return "E2E_EXPECTED_VERSION differs from the installed diagnostic CLI candidate"
    return ""


def execute(lane: str, extra: list[str]) -> int:
    directory = Path("test-results") / lane
    fresh(directory)
    command = pytest_command(lane, extra)
    reason, blocked, code = "", False, 0
    try:
        if lane in {"azure-e2e", "local-e2e"}:
            reason = azure_preflight(local=lane == "local-e2e")
            blocked = bool(reason)
        if lane == "host-smoke":
            command = ["func", "start", "managed-host-smoke"]
            blocked = bool(doctor(live=True))
            if blocked:
                reason = "Missing required host-smoke prerequisites"
            else:
                code = host_smoke(directory)
        elif not blocked:
            with tempfile.TemporaryDirectory(prefix="doctor-evidence-") as temporary:
                raw = Path(temporary) / "junit.xml"
                actual = [*command[:-1], "--junitxml=" + str(raw)]
                code = run(actual, directory / "logs/runner.log", 1200)
                if raw.exists():
                    (directory / "junit.xml").write_text(redact(raw.read_text()))
    except KeyboardInterrupt:
        code, reason = 130, "Interrupted; owned processes terminated"
    except (OSError, ValueError) as error:
        code, reason = 2, str(error)
    try:
        summary = collect(directory, command, 2 if blocked else code)
    except (ET.ParseError, ValueError) as error:
        summary = Summary(
            1,
            lane,
            tuple(command),
            0,
            0,
            0,
            0,
            "INCOMPLETE",
            2,
            reason=f"Invalid evidence: {error}",
        )
    summary = replace(
        summary,
        reason=reason or summary.reason,
        status="INCOMPLETE" if blocked else summary.status,
        candidate_version=os.environ.get("E2E_EXPECTED_VERSION", ""),
    )
    publish(save(directory, summary))
    return summary.exit_code


def aggregate(lane: str, outcomes: list[Summary]) -> int:
    status: Status = "PASS"
    required = [item for item in outcomes if item.status != "NOT_APPLICABLE"]
    if any(item.status == "FAIL" for item in required):
        status = "FAIL"
    elif not required or any(item.status != "PASS" for item in required):
        status = "INCOMPLETE"
    directory = Path("test-results") / lane
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "lanes.json").write_text(json.dumps([asdict(item) for item in outcomes], indent=2))
    summary = Summary(
        1,
        lane,
        ("make", lane),
        sum(s.selected for s in outcomes),
        sum(s.passed for s in outcomes),
        sum(s.failed for s in outcomes),
        sum(s.skipped for s in outcomes),
        status,
        int(status != "PASS"),
        scope="FULL_LOCAL" if lane == "verify" else "LOCAL_INTEGRATION",
        reason="; ".join(f"{s.lane}={s.status}" for s in outcomes),
    )
    publish(save(directory, summary))
    return summary.exit_code


def run_targets(lane: str, targets: tuple[str, ...]) -> int:
    directory = Path("test-results") / lane
    fresh(directory)
    outcomes: list[Summary] = []
    for target in targets:
        path = Path("test-results") / target / "summary.json"
        path.unlink(missing_ok=True)
        code = run(["make", target], directory / "logs" / f"{target}.log", 1800)
        if path.exists():
            summary = Summary(**json.loads(path.read_text()))
            if code and summary.status == "PASS":
                summary = replace(summary, status="FAIL", exit_code=code)
        else:
            summary = Summary(
                1,
                target,
                ("make", target),
                int(target == "check"),
                int(target == "check" and code == 0),
                int(code != 0),
                0,
                ("FAIL" if code else "PASS") if target == "check" else "INCOMPLETE",
                code or int(target != "check"),
                reason="Required lane summary missing",
            )
        outcomes.append(summary)
    if lane == "integration":
        for consumer in ("action-integration", "v1-consumer-smoke", "cookbook-soak"):
            outcomes.append(
                Summary(
                    1,
                    consumer,
                    ("GitHub Actions",),
                    0,
                    0,
                    0,
                    0,
                    "NOT_APPLICABLE",
                    0,
                    reason="Workflow-only consumer; not executed locally",
                )
            )
        source = Path("test-results/host-smoke")
        for pattern, destination in (("junit/*.xml", "junit"), ("logs/*", "logs")):
            for artifact in source.glob(pattern):
                target_path = directory / destination / artifact.name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(artifact, target_path)
    return aggregate(lane, outcomes)


def focused(lane: str, command: list[str]) -> int:
    directory = Path("test-results") / lane
    fresh(directory)
    code = run(command, directory / "logs/runner.log", 1200)
    summary = Summary(
        1,
        lane,
        tuple(command),
        1,
        int(code == 0),
        int(code != 0),
        0,
        "PASS" if code == 0 else "FAIL",
        code,
    )
    publish(save(directory, summary))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "lane",
        choices=(
            "test",
            "host-smoke",
            "integration",
            "verify",
            "azure-e2e",
            "local-e2e",
            "doctor",
            "report",
            "clean",
            "focused",
        ),
    )
    args, extra = parser.parse_known_args()
    match args.lane:
        case "doctor":
            return doctor()
        case "clean":
            clean(Path.cwd())
            return 0
        case "report":
            return report(Path("test-results"))
        case "verify":
            return run_targets(
                "verify", ("check", "test", "integration", "wheel-smoke", "build", "docs")
            )
        case "integration":
            return run_targets("integration", ("cli-smoke", "host-smoke"))
        case "focused":
            return focused(extra[0], [sys.executable, *extra[1:]])
        case _:
            return execute(args.lane, extra)


if __name__ == "__main__":
    raise SystemExit(main())
