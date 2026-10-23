"""Owned, exact exceptions with a maximum 90-day validity window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from tools.security_report import JSON, EvidenceError, identifier, integer, mapping, sequence, text


@dataclass(frozen=True, slots=True)
class ExceptionRule:
    id: str
    package: str
    file: str
    line: int
    kind: str
    expires: date
    added: date


def parse_exceptions(data: JSON, today: date) -> tuple[ExceptionRule, ...]:
    rules: list[ExceptionRule] = []
    for entry in sequence(data):
        item = mapping(entry)
        text(item["reason"])
        text(item["owner"])
        added = date.fromisoformat(text(item["added"]))
        expires = date.fromisoformat(text(item["expires"]))
        if not 0 < (expires - added).days <= 90 or added > today:
            raise EvidenceError("invalid exception validity window")
        rule = ExceptionRule(
            identifier(item["id"]),
            identifier(item["package"]) if "package" in item else "",
            identifier(item["file"]) if "file" in item else "",
            integer(item.get("line", 0)),
            text(item["kind"]),
            expires,
            added,
        )
        if rule.kind not in {"fix-not-available", "not-affected", "reviewed-static"}:
            raise EvidenceError("unknown exception kind")
        if any(
            (r.id, r.package, r.file, r.line) == (rule.id, rule.package, rule.file, rule.line)
            for r in rules
        ):
            raise EvidenceError("duplicate exception")
        rules.append(rule)
    return tuple(rules)
