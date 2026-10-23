"""Offline requirements traversal with per-tree work budgets."""

from collections.abc import Iterator
from pathlib import Path
from typing import Final

from azure_functions_doctor.inspection import read_inspection_text, refuse_inspection
from azure_functions_doctor.inspection_gaps import InspectionGap, record_gap
from azure_functions_doctor.requirements_directives import parse_include_directive

MAX_REQUIREMENTS_FILES: Final = 128
MAX_REQUIREMENTS_BYTES: Final = 16 * 1024 * 1024
MAX_REQUIREMENTS_DEPTH: Final = 10


def iter_requirements_files(
    source: Path, initial_content: str | None = None
) -> Iterator[tuple[Path, str]]:
    """Yield each in-root manifest once; budgets include the root manifest."""
    root = source.parent.resolve()
    seen: set[Path] = set()
    total = 0

    def walk(path: Path, depth: int, content: str | None = None) -> Iterator[tuple[Path, str]]:
        nonlocal total
        resolved = path.resolve()
        if resolved in seen:
            return
        if depth >= MAX_REQUIREMENTS_DEPTH or len(seen) >= MAX_REQUIREMENTS_FILES:
            refuse_inspection(path)
            return
        seen.add(resolved)
        if content is None:
            try:
                content = read_inspection_text(path)
            except (OSError, ValueError):
                return
        total += len(content.encode("utf-8"))
        if total > MAX_REQUIREMENTS_BYTES:
            refuse_inspection(path)
            return
        yield path, content
        for line_no, line in enumerate(content.splitlines(), 1):
            directive = parse_include_directive(line)
            if directive is None or "://" in directive.reference:
                continue
            include = path.parent / directive.reference
            if not include.resolve().is_relative_to(root):
                record_gap(InspectionGap(path.absolute(), line_no, directive.reference))
                continue
            if directive.constraint:
                continue
            yield from walk(include, depth + 1)

    yield from walk(source.absolute(), 0, initial_content)
