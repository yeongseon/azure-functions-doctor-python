"""Bounded regular-file reads for static inspection, never device or FIFO reads."""

import ast
import json
import os
from pathlib import Path
import stat
import tomllib
from typing import Final, Literal, TypeAlias

from azure_functions_doctor.inspection_gaps import InspectionGap, record_gap
from azure_functions_doctor.source_cache import parse_source

MAX_FILE_BYTES: Final = 4 * 1024 * 1024
MAX_JSON_DEPTH: Final = 100
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


def refuse_inspection(path: Path) -> None:
    record_gap(InspectionGap(path.absolute(), 1, "", "inspection limit"))


def read_inspection_text(
    path: Path,
    *,
    encoding: Literal["utf-8", "utf-8-sig"] = "utf-8-sig",
    universal_newlines: bool = True,
) -> str:
    """Reject symlinks and nonregular files before a bounded, nonblocking read."""
    try:
        text = _read_text(path, encoding)
        return text.replace("\r\n", "\n").replace("\r", "\n") if universal_newlines else text
    except FileNotFoundError:
        raise
    except (OSError, ValueError, MemoryError):
        refuse_inspection(path)
        raise


def _read_text(path: Path, encoding: Literal["utf-8", "utf-8-sig"]) -> str:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise OSError("Inspection skips symbolic links")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise OSError("Inspection requires a regular file")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise OSError("Inspection requires a regular file of at most 4 MiB")
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES or b"\x00" in data:
        raise OSError("Inspection skips oversized or binary files")
    return data.decode(encoding)


def parse_inspection_json(text: str, path: Path) -> JsonValue:
    """Scan nesting in linear time without interpreting brackets inside JSON strings."""
    depth = 0
    quoted = False
    escaped = False
    try:
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > MAX_JSON_DEPTH:
                    raise OSError("Inspection skips JSON deeper than 100 levels")
            elif char in "]}":
                depth -= 1
        value: JsonValue = json.loads(text)
        return value
    except (OSError, ValueError, RecursionError, MemoryError):
        refuse_inspection(path)
        raise


def read_inspection_json(
    path: Path, *, encoding: Literal["utf-8", "utf-8-sig"] = "utf-8-sig"
) -> JsonValue:
    return parse_inspection_json(read_inspection_text(path, encoding=encoding), path)


def read_inspection_toml(path: Path) -> dict[str, JsonValue]:
    try:
        return tomllib.loads(read_inspection_text(path, encoding="utf-8", universal_newlines=False))
    except (ValueError, RecursionError, MemoryError) as exc:
        refuse_inspection(path)
        raise OSError(f"Inspection skips TOML ({type(exc).__name__})") from None


def contained_inspection_path(root: Path, reference: str) -> Path:
    """Check containment without resolving away a symlink before the reader sees it."""
    candidate = root / reference
    if Path(reference).is_absolute() or not candidate.resolve().is_relative_to(root.resolve()):
        record_gap(InspectionGap(root.absolute() / "requirements.txt", 1, reference))
        raise OSError("Inspection reference leaves the project root")
    return candidate


def check_python_parser(source: str, path: Path) -> None:
    try:
        tree = parse_source(source)
        for _ in ast.walk(tree):
            continue
    except SyntaxError as exc:
        if exc.msg == "too many nested parentheses":
            refuse_inspection(path)
            raise OSError("Inspection skips Python parser nesting limit") from None
        return
    except (RecursionError, MemoryError, ValueError):
        refuse_inspection(path)
        raise OSError("Inspection skips Python parser resource failure") from None
