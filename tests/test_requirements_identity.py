from pathlib import Path

import pytest

from azure_functions_doctor.handlers._helpers import (
    _iter_requirements_txt_lines,
    _iter_requirements_with_location,
    _parse_requirements_names,
    _project_declares_openapi_dep,
    _project_declares_validation_dep,
)
from azure_functions_doctor.inspection_gaps import collect_inspection_gaps


@pytest.mark.parametrize("reference", ["./common.txt", "nested/../common.txt", "alias.txt"])
def test_both_walkers_share_canonical_identity_without_duplicate_findings(
    tmp_path: Path, reference: str
) -> None:
    root = tmp_path / "requirements.txt"
    (tmp_path / "nested").mkdir()
    (tmp_path / "common.txt").write_text("numpy\n")
    (tmp_path / "alias.txt").symlink_to(tmp_path / "common.txt")
    content = f"-r {reference}\n-r common.txt\n-r {reference}\n"
    root.write_text(content)
    with collect_inspection_gaps() as gaps:
        flattened = _iter_requirements_txt_lines(content, root)
        located = _iter_requirements_with_location(root)
    assert flattened == ["numpy"]
    assert located == [(tmp_path / "common.txt", 1, "numpy")]
    assert gaps == []


def test_integration_dependencies_follow_multilevel_root_alias(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "manifest.txt").write_text("-r ./sub/child.txt\n")
    (tmp_path / "requirements.txt").symlink_to(tmp_path / "manifest.txt")
    (tmp_path / "sub/child.txt").write_text("-r ../common.txt\n")
    (tmp_path / "common.txt").write_text(
        "azure-functions-openapi\nazure-functions-validation\nazure-functions-worker\n"
    )
    content = (tmp_path / "manifest.txt").read_text()
    assert _parse_requirements_names(content, tmp_path / "requirements.txt") == {
        "azure-functions-openapi",
        "azure-functions-validation",
        "azure-functions-worker",
    }
    assert not _project_declares_openapi_dep(tmp_path)
    assert not _project_declares_validation_dep(tmp_path)


def test_outside_symlink_include_remains_visibly_refused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "outside.txt").write_text("CANARY_OUTSIDE\n")
    (project / "alias.txt").symlink_to(tmp_path / "outside.txt")
    root = project / "requirements.txt"
    root.write_text("-r alias.txt\n")
    with collect_inspection_gaps() as gaps:
        assert _iter_requirements_txt_lines(root.read_text(), root) == []
        assert _iter_requirements_with_location(root) == []
    assert gaps
