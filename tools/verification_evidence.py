"""Versioned evidence and credential masking for verification tooling only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Literal
import xml.etree.ElementTree as ET

Status = Literal["PASS", "FAIL", "INCOMPLETE", "NOT_APPLICABLE"]
REMOTE_ASSERTIONS = frozenset(
    {"test_deployed_http_trigger_responds", "test_doctor_passes_on_example_project"}
)


@dataclass(frozen=True, slots=True)
class Summary:
    schema_version: int
    lane: str
    command: tuple[str, ...]
    selected: int
    passed: int
    failed: int
    skipped: int
    status: Status
    exit_code: int
    supporting_files: tuple[str, ...] = ()
    coverage: float | None = None
    scope: str = "PARTIAL"
    reason: str = ""
    candidate_version: str = ""
    artifact_sha256: str = ""
    deployed_version_match: Status = "NOT_APPLICABLE"


def redact(text: str) -> str:
    text = re.sub(r"(?im)(authorization[\"']?\s*[:=]\s*)[^\r\n<\"]+", r"\1[REDACTED]", text)
    text = re.sub(r"([\w+.-]+://)[^/\s<>\"']*@", r"\1[REDACTED]@", text)
    text = re.sub(r"(?i)(DefaultEndpointsProtocol=)[^\s<\"']+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)(?<![\w-])((?:[\w-]*(?:token|password|secret|connection[_-]?string)|AccountKey|"
        r"SharedAccessSignature|AzureWebJobsStorage|x-functions-key|code|sig|sas|api[_-]?key)"
        r"[\"']?\s*[:=]\s*[\"']?)[^\s;&<\"']+",
        r"\1[REDACTED]",
        text,
    )
    for key, value in os.environ.items():
        if len(value) >= 6 and re.search(
            r"(?i)secret|token|password|conn|accountkey|functions.key", key
        ):
            text = text.replace(value, "[REDACTED]")
    return text


def environment() -> dict[str, str]:
    metadata = {
        "python": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
    }
    for package in ("azure-functions-doctor", "azure-functions", "hatch", "pytest"):
        try:
            metadata[package] = version(package)
        except PackageNotFoundError:
            metadata[package] = "not installed"
    for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "E2E_BASE_URL", "E2E_EXPECTED_VERSION"):
        if key in os.environ:
            metadata[key] = redact(os.environ[key])
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=False
        )
        metadata["commit"] = result.stdout.strip() if result.returncode == 0 else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        metadata["commit"] = "unavailable"
    return metadata


def collect(directory: Path, command: list[str], exit_code: int) -> Summary:
    cases = [
        case
        for path in directory.rglob("*junit.xml")
        for case in ET.parse(path).getroot().iter("testcase")
    ]
    skipped = sum(case.find("skipped") is not None for case in cases)
    failed = sum(
        case.find("failure") is not None or case.find("error") is not None for case in cases
    )
    passed = len(cases) - skipped - failed
    status: Status = "PASS"
    reason = ""
    if failed or exit_code not in (0, 5):
        status, reason = "FAIL", "Test/process failure, collection error, interruption or timeout"
    elif not passed or skipped:
        status, reason = "INCOMPLETE", "Required tests empty, all skipped or unexpectedly skipped"
    elif directory.name in {"azure-e2e", "local-e2e"} and not REMOTE_ASSERTIONS.issubset(
        {case.get("name", "") for case in cases}
    ):
        status, reason = "INCOMPLETE", "Required remote assertion missing"
    elif exit_code:
        status, reason = "FAIL", "Nonzero pytest exit"
    coverage = None
    if (directory / "coverage.xml").exists():
        coverage = float(ET.parse(directory / "coverage.xml").getroot().get("line-rate", "0"))
    return Summary(
        1,
        directory.name,
        tuple(command),
        len(cases),
        passed,
        failed,
        skipped,
        status,
        exit_code or int(status != "PASS"),
        coverage=coverage,
        reason=reason,
    )


def publish(summary: Summary) -> None:
    text = redact(
        f"{summary.lane}: {summary.status} | scope={summary.scope} selected={summary.selected} "
        f"passed={summary.passed} failed={summary.failed} skipped={summary.skipped} "
        f"exit={summary.exit_code} | {summary.reason}"
    )
    print(text)
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write(f"\n- {text}\n")


def save(directory: Path, summary: Summary) -> Summary:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.rglob("*"):
        if path.is_file():
            path.write_text(redact(path.read_text(encoding="utf-8")), encoding="utf-8")
    (directory / "environment.json").write_text(
        redact(json.dumps(environment(), indent=2)) + "\n", encoding="utf-8"
    )
    summary = replace(
        summary,
        command=tuple(redact(part) for part in summary.command),
        reason=redact(summary.reason),
        supporting_files=tuple(
            str(path)
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path.name != "summary.json"
        ),
    )
    serialized = redact(json.dumps(asdict(summary), indent=2))
    (directory / "summary.json").write_text(serialized + "\n", encoding="utf-8")
    return Summary(**json.loads(serialized))


def report(root: Path) -> int:
    paths = sorted(root.rglob("summary.json"))
    for path in paths:
        publish(Summary(**json.loads(path.read_text(encoding="utf-8"))))
    if not paths:
        print("No saved verification evidence")
    return 0 if paths else 1
