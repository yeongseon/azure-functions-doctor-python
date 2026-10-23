from pathlib import Path

import pytest

from azure_functions_doctor.handlers._helpers import (
    _iter_requirements_txt_lines,
    _iter_requirements_with_location,
)
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps

SPELLINGS = [
    "-{} {{}}",
    "-{}\t{{}}",
    "-{}   {{}}",
    "-{}{{}}",
    "--{} {{}}",
    "--{}\t{{}}",
    "--{}={{}}",
]


@pytest.mark.parametrize("walker", ["flat", "location"])
@pytest.mark.parametrize("spelling", SPELLINGS)
@pytest.mark.parametrize("kind", ["constraint", "requirement"])
@pytest.mark.parametrize("outside", [False, True])
def test_directive_spellings_share_containment_and_constraint_semantics(
    tmp_path: Path, walker: str, spelling: str, kind: str, outside: bool
) -> None:
    root = tmp_path / "app"
    root.mkdir()
    reference = "../common.txt" if outside else "common.txt"
    target = (root.parent if outside else root) / "common.txt"
    target.write_text("numpy\n")
    option = kind if spelling.startswith("--") else kind[0]
    content = spelling.format(option).format(reference) + "\n"
    req = root / "requirements.txt"
    req.write_text(content)
    with collect_inspection_gaps() as gaps:
        entries = (
            _iter_requirements_txt_lines(content, req)
            if walker == "flat"
            else [line for _, _, line in _iter_requirements_with_location(req)]
        )
    assert entries == (["numpy"] if kind == "requirement" and not outside else [])
    assert [gap.reference for gap in gaps] == ([reference] if outside else [])


@pytest.mark.parametrize("option", ["-r", "-c"])
@pytest.mark.parametrize("walker", ["flat", "location"])
def test_short_equals_is_part_of_filename(tmp_path: Path, option: str, walker: str) -> None:
    (tmp_path / "=common.txt").write_text("numpy\n")
    req = tmp_path / "requirements.txt"
    req.write_text(option + "=common.txt\n")
    entries = (
        _iter_requirements_txt_lines(req.read_text(), req)
        if walker == "flat"
        else [line for _, _, line in _iter_requirements_with_location(req)]
    )
    assert entries == (["numpy"] if option == "-r" else [])
