"""Read candidate identity from wheel metadata without importing candidate code."""

from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


def wheel_identity(wheel: Path) -> tuple[str, str]:
    with ZipFile(wheel) as archive:
        entries = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(entries) != 1:
            raise ValueError("Expected one candidate metadata record")
        metadata = BytesParser().parsebytes(archive.read(entries[0]))
    name, version = metadata.get("Name", ""), metadata.get("Version", "")
    if not name or not version:
        raise ValueError("Candidate identity missing")
    return name, version
