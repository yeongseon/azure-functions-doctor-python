#!/usr/bin/env python3
"""Read the counts file written by ``azure-functions-doctor doctor --summary-json``.

Reads structured counters instead of scraping terminal text. The file is validated first
(exact keys, integer counts, boolean ``gate_failed``), then one stable line is printed.
The exit status mirrors ``gate_failed`` so it can be combined with doctor's own exit code.

Usage: ``python read_doctor_summary.py doctor-summary.json``
Exit codes: 0 = no required failure, 1 = required failure, 2 = unreadable/invalid summary.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

COUNT_KEYS = ("passed", "warned", "failed", "skipped")
EXPECTED_KEYS = frozenset((*COUNT_KEYS, "gate_failed"))


def load_summary(path: Path) -> dict[str, int | bool]:
    """Return the validated summary or raise ``ValueError`` describing the problem."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read summary: {type(exc).__name__}") from exc
    if not isinstance(data, dict) or set(data) != EXPECTED_KEYS:
        raise ValueError(f"summary keys must be exactly {sorted(EXPECTED_KEYS)}")
    for key in COUNT_KEYS:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    if not isinstance(data["gate_failed"], bool):
        raise ValueError("gate_failed must be a boolean")
    return data


def format_summary(summary: dict[str, int | bool]) -> str:
    counts = " ".join(f"{key}={summary[key]}" for key in COUNT_KEYS)
    return f"doctor: {counts} gate_failed={str(summary['gate_failed']).lower()}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: read_doctor_summary.py <doctor-summary.json>", file=sys.stderr)
        return 2
    try:
        summary = load_summary(Path(argv[1]))
    except ValueError as exc:
        print(f"invalid doctor summary: {exc}", file=sys.stderr)
        return 2
    print(format_summary(summary))
    return 1 if summary["gate_failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
