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


def read_xml_root(path: Path) -> ET.Element:
    """Parse a locally generated report, refusing entity declarations."""
    data = path.read_bytes()
    if b"<!ENTITY" in data.upper():
        raise ValueError("XML reports must not declare entities")
    return ET.fromstring(data)


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


_REDACTED = "[REDACTED]"
_QUOTED = r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'"
_AUTHORIZATION = re.compile(
    r"(?im)(?P<key>(?:proxy-)?authorization[\"']?\s*[:=]\s*)(?P<value>" + _QUOTED + r"|[^\r\n\"<]+)"
)
_URL_CREDENTIALS = re.compile(r"([\w+.-]+://)[^/@\s\"']+@")
_SECRET_FIELD = re.compile(
    r"(?i)(?<![\w-])(?P<key>(?:[\w.-]*(?:token|password|passwd|secret|api[_-]?key|"
    r"connection[_-]?string)|AccountKey|SharedAccessKey|SharedAccessSignature|"
    r"AzureWebJobsStorage|InstrumentationKey|x-functions-key|code|sig|sas)"
    r"[\"']?\s*[:=]\s*)(?P<value>" + _QUOTED + r"|[^\s;&<>\"',]+)"
)
_SECRET_ENV_NAME = re.compile(
    r"(?i)secret|token|password|conn|string|accountkey|functions.key|api.?key|sas"
)
_TEXT_SUFFIXES = frozenset({".log", ".txt", ".xml", ".json", ".md"})


def _mask(match: re.Match[str]) -> str:
    value = match.group("value")
    quote = value[0] if value[:1] in {'"', "'"} else ""
    return f"{match.group('key')}{quote}{_REDACTED}{quote}"


def _known_secrets() -> list[str]:
    values = {
        value
        for key, value in os.environ.items()
        if len(value) >= 6 and _SECRET_ENV_NAME.search(key)
    }
    escaped = {json.dumps(value)[1:-1] for value in values}
    return sorted(values | escaped, key=len, reverse=True)


def redact(text: str) -> str:
    for value in _known_secrets():
        text = text.replace(value, _REDACTED)
    text = _AUTHORIZATION.sub(_mask, text)
    text = _URL_CREDENTIALS.sub(r"\1" + _REDACTED + "@", text)
    return _SECRET_FIELD.sub(_mask, text)


def redact_json(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, (list, tuple)):
        return [redact_json(item) for item in value]
    if isinstance(value, dict):
        return {redact(str(key)): redact_json(item) for key, item in value.items()}
    return value


def dump_json(value: object) -> str:
    return json.dumps(redact_json(value), indent=2) + "\n"


def _redact_file_text(suffix: str, text: str) -> str:
    if suffix == ".json":
        try:
            return dump_json(json.loads(text))
        except ValueError:
            return redact(text)
    return redact(text)


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
        for case in read_xml_root(path).iter("testcase")
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
        coverage = float(read_xml_root(directory / "coverage.xml").get("line-rate", "0"))
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
        if path.is_symlink() or not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        redacted = _redact_file_text(path.suffix, original)
        if redacted != original:
            path.write_text(redacted, encoding="utf-8")
    (directory / "environment.json").write_text(dump_json(environment()), encoding="utf-8")
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
    serialized = dump_json(asdict(summary))
    (directory / "summary.json").write_text(serialized, encoding="utf-8")
    return Summary(**json.loads(serialized))


def report(root: Path) -> int:
    paths = sorted(root.rglob("summary.json"))
    for path in paths:
        publish(Summary(**json.loads(path.read_text(encoding="utf-8"))))
    if not paths:
        print("No saved verification evidence")
    return 0 if paths else 1
