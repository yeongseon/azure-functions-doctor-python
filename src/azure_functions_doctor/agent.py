"""Thin, deterministic adapter for agent consumers of doctor reports."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import TypeAlias

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class AgentReportError(ValueError):
    """Raised when an input report does not satisfy the agent adapter contract."""

    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class AgentFinding:
    """Evidence needed to explain one deterministic doctor finding."""

    rule_id: str
    status: str
    summary: str
    evidence: str
    expected: str
    actual: str
    source_url: str
    last_verified: str


@dataclass(frozen=True, slots=True)
class AgentReport:
    """Finding Contract v2 projected into an agent-friendly interface."""

    schema_version: str
    findings: tuple[AgentFinding, ...]
    sarif: dict[str, JsonValue] | None = None


def _required_string(value: JsonValue, field: str) -> str:
    if not isinstance(value, str):
        raise AgentReportError(f"finding field '{field}' must be a string")
    return value


def _parse_finding(raw: JsonValue) -> AgentFinding:
    if not isinstance(raw, dict):
        raise AgentReportError("each finding must be a JSON object")
    analysis = raw.get("analysis")
    if not isinstance(analysis, dict) or analysis.get("type") != "deterministic":
        raise AgentReportError("agent adapter accepts deterministic findings only")
    return AgentFinding(
        rule_id=_required_string(raw.get("rule_id"), "rule_id"),
        status=_required_string(raw.get("status"), "status"),
        summary=_required_string(raw.get("value"), "value"),
        evidence=_required_string(raw.get("evidence", ""), "evidence"),
        expected=_required_string(raw.get("expected", ""), "expected"),
        actual=_required_string(raw.get("actual", ""), "actual"),
        source_url=_required_string(raw.get("source_url", ""), "source_url"),
        last_verified=_required_string(raw.get("last_verified", ""), "last_verified"),
    )


def _read_json(path: Path) -> dict[str, JsonValue]:
    try:
        value: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentReportError(f"cannot read JSON report {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentReportError(f"JSON report {path} must contain an object")
    return value


def load_agent_report(json_path: Path, *, sarif_path: Path | None = None) -> AgentReport:
    """Load existing doctor JSON and optional SARIF without adding analysis."""
    report = _read_json(json_path)
    schema_version = report.get("schema_version")
    if schema_version != "2.0":
        raise AgentReportError("agent adapter requires Finding Contract v2 (schema_version 2.0)")
    raw_sections = report.get("results")
    if not isinstance(raw_sections, list):
        raise AgentReportError("doctor report 'results' must be a list")

    findings: list[AgentFinding] = []
    for raw_section in raw_sections:
        if not isinstance(raw_section, dict):
            raise AgentReportError("each doctor report section must be a JSON object")
        raw_items = raw_section.get("items")
        if not isinstance(raw_items, list):
            raise AgentReportError("each doctor report section must contain an items list")
        findings.extend(_parse_finding(raw_item) for raw_item in raw_items)

    sarif = _read_json(sarif_path) if sarif_path is not None else None
    return AgentReport(schema_version=schema_version, findings=tuple(findings), sarif=sarif)


def explain_failures(report: AgentReport) -> tuple[AgentFinding, ...]:
    """Return warn/fail evidence suitable for a “why did this fail?” answer."""
    return tuple(finding for finding in report.findings if finding.status in {"warn", "fail"})
