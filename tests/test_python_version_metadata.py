from __future__ import annotations

from email.parser import BytesParser
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib
from zipfile import ZipFile

from packaging.specifiers import SpecifierSet
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PYTHON = SpecifierSet(">=3.11,<3.15")


@pytest.fixture(scope="module")
def built_metadata(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    output = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(output)],
        cwd=PROJECT_ROOT,
        check=True,
    )

    wheel = next(output.glob("*.whl"))
    with ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        wheel_metadata = archive.read(metadata_name).decode()

    sdist = next(output.glob("*.tar.gz"))
    with tarfile.open(sdist) as archive:
        pkg_info = next(
            member for member in archive.getmembers() if member.name.endswith("/PKG-INFO")
        )
        extracted = archive.extractfile(pkg_info)
        assert extracted is not None
        sdist_metadata = extracted.read().decode()
    return wheel_metadata, sdist_metadata


def test_requires_python_declares_supported_range() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    declared = SpecifierSet(project["requires-python"])

    assert declared == SUPPORTED_PYTHON


def test_classifiers_match_supported_python_minors() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    prefix = "Programming Language :: Python :: 3."

    classified_minors = {
        classifier.removeprefix(prefix)
        for classifier in project["classifiers"]
        if classifier.startswith(prefix)
    }

    assert classified_minors == {"11", "12", "13", "14"}


@pytest.mark.parametrize("artifact_index", [0, 1], ids=["wheel", "sdist"])
def test_built_artifact_requires_python_matches_supported_range(
    built_metadata: tuple[str, str], artifact_index: int
) -> None:
    metadata = BytesParser().parsebytes(built_metadata[artifact_index].encode())

    declared = SpecifierSet(metadata["Requires-Python"])

    assert declared == SUPPORTED_PYTHON
