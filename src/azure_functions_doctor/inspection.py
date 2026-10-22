"""Bounded regular-file reads for static inspection, never device or FIFO reads."""

import os
from pathlib import Path
import stat
from typing import Final

MAX_FILE_BYTES: Final = 4 * 1024 * 1024


def read_inspection_text(path: Path) -> str:
    """Reject symlinks and nonregular files before a bounded, nonblocking read."""
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise OSError("Inspection skips symbolic links")
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise OSError("Inspection requires a regular file of at most 4 MiB")
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES or b"\x00" in data:
        raise OSError("Inspection skips oversized or binary files")
    return data.decode("utf-8-sig")
