#!/usr/bin/env python3
"""Offline structural check for the SARIF file written by ``doctor --format sarif``.

This is a *structural* check, not validation against the official SARIF 2.1.0 JSON
Schema: that schema is large and lives on the network, and this example must run offline
with only the standard library. It verifies the parts Code Scanning consumers rely on:
the version, a tool driver, unique rule ids, and that each result has a known level, a
message, a ``ruleId`` that appears in the driver rules, and well-formed locations.

Usage: ``python check_sarif_shape.py doctor.sarif``  (exit 0 = ok, 1 = problems found)
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

SARIF_VERSION = "2.1.0"
LEVELS = frozenset({"none", "note", "warning", "error"})


def check_sarif_shape(document: Any) -> list[str]:
    """Return a list of structural problems; an empty list means the shape is fine."""
    problems: list[str] = []
    if not isinstance(document, dict):
        return ["top level must be a JSON object"]
    if document.get("version") != SARIF_VERSION:
        problems.append(f"version must be {SARIF_VERSION!r}")
    runs = document.get("runs")
    if not isinstance(runs, list) or not runs:
        return [*problems, "runs must be a non-empty list"]
    for index, run in enumerate(runs):
        problems.extend(_check_run(run, f"runs[{index}]"))
    return problems


def _check_run(run: Any, where: str) -> list[str]:
    if not isinstance(run, dict):
        return [f"{where} must be an object"]
    driver = run.get("tool", {}).get("driver") if isinstance(run.get("tool"), dict) else None
    if not isinstance(driver, dict) or not driver.get("name"):
        return [f"{where}.tool.driver.name is required"]
    problems: list[str] = []
    rules = driver.get("rules", [])
    rule_ids: list[str] = [r.get("id", "") for r in rules if isinstance(r, dict)]
    if not isinstance(rules, list) or not all(rule_ids):
        problems.append(f"{where}.tool.driver.rules entries need an id")
    if len(set(rule_ids)) != len(rule_ids):
        problems.append(f"{where}.tool.driver.rules ids must be unique")
    results = run.get("results", [])
    if not isinstance(results, list):
        return [*problems, f"{where}.results must be a list"]
    for index, result in enumerate(results):
        problems.extend(_check_result(result, set(rule_ids), f"{where}.results[{index}]"))
    return problems


def _check_result(result: Any, rule_ids: set[str], where: str) -> list[str]:
    if not isinstance(result, dict):
        return [f"{where} must be an object"]
    problems: list[str] = []
    if result.get("ruleId") not in rule_ids:
        problems.append(f"{where}.ruleId must match a driver rule id")
    if result.get("level") not in LEVELS:
        problems.append(f"{where}.level must be one of {sorted(LEVELS)}")
    message = result.get("message")
    if not isinstance(message, dict) or not message.get("text"):
        problems.append(f"{where}.message.text is required")
    for location in result.get("locations", []):
        uri = (
            location.get("physicalLocation", {}).get("artifactLocation", {}).get("uri")
            if isinstance(location, dict)
            else None
        )
        if not isinstance(uri, str) or not uri:
            problems.append(f"{where}.locations[].physicalLocation.artifactLocation.uri required")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_sarif_shape.py <file.sarif>", file=sys.stderr)
        return 2
    try:
        document = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read SARIF: {type(exc).__name__}", file=sys.stderr)
        return 1
    problems = check_sarif_shape(document)
    for problem in problems:
        print(f"SARIF shape problem: {problem}", file=sys.stderr)
    if not problems:
        print("SARIF structural check passed (not full JSON Schema validation).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
