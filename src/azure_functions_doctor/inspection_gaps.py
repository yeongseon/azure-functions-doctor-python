"""Rule-scoped evidence for references excluded by inspection containment."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from azure_functions_doctor.handlers._helpers import HandlerResult


@dataclass(frozen=True, slots=True)
class InspectionGap:
    file: Path
    line: int
    reference: str
    kind: str = "requirements include"


_gaps: ContextVar[list[InspectionGap] | None] = ContextVar("inspection_gaps", default=None)


@contextmanager
def collect_inspection_gaps() -> Iterator[list[InspectionGap]]:
    gaps: list[InspectionGap] = []
    token = _gaps.set(gaps)
    try:
        yield gaps
    finally:
        _gaps.reset(token)


def record_gap(gap: InspectionGap) -> None:
    gaps = _gaps.get()
    if gaps is not None and gap not in gaps:
        gaps.append(gap)


def incomplete_result(gaps: list[InspectionGap], root: Path) -> "HandlerResult":
    locations: list[dict[str, object]] = []
    for gap in gaps:
        message = (
            f"{gap.kind.capitalize()} {json.dumps(gap.reference)} resolves outside the "
            "project root and was not inspected; dependency/source checks are incomplete. "
            "Fix: vendor/copy the file inside the project or run doctor from the monorepo "
            "root with --path."
        )
        locations.append(
            {"file": gap.file.relative_to(root).as_posix(), "line": gap.line, "message": message}
        )
    first = gaps[0]
    return {
        "status": "fail",
        "severity": "warning",
        "gate": False,
        "detail": "\n".join(str(location["message"]) for location in locations),
        "file": first.file.relative_to(root).as_posix(),
        "line": first.line,
        "locations": locations,
    }
