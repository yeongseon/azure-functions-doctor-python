"""Traversal governance tests (issue #393).

Two layers:

1. **Structural**: no module outside ``_helpers.py`` may call ``Path.rglob``
   directly — all project traversal must flow through the shared
   ``iter_project_files`` helper so ``EXCLUDED_PROJECT_DIRS`` and the user's
   ``[tool.azure-functions-doctor].exclude`` globs are always honored. This is
   what prevents the next rule from reintroducing the venv/node_modules scans.
2. **Behavioral**: the helper excludes virtualenvs, dependency trees, and
   user-excluded globs, and ``check_dev_storage_connection`` skips template
   files like ``local.settings.sample.json``.
"""

from pathlib import Path
from typing import cast

from azure_functions_doctor.handlers._helpers import (
    Rule,
    iter_project_files,
    reset_extra_excludes,
    set_extra_excludes,
)

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "azure_functions_doctor"


def test_no_raw_rglob_outside_the_shared_traversal_helper() -> None:
    """Only _helpers.py may call rglob; every other module uses the helper."""
    offenders: list[str] = []
    for module in SRC_ROOT.rglob("*.py"):
        if module.name == "_helpers.py":
            continue
        text = module.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if ".rglob(" in line or (".glob(" in line and "iter_project" not in line):
                offenders.append(f"{module.relative_to(SRC_ROOT)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "Raw traversal detected outside the shared helper "
        "(use azure_functions_doctor.handlers._helpers.iter_project_files):\n"
        + "\n".join(offenders)
    )


def test_iter_project_files_skips_dependency_trees(tmp_path: Path) -> None:
    """venv (no dot), node_modules, and site-packages are never yielded."""
    for rel in (
        "venv/lib/site-pkg/keep.py",
        "node_modules/pkg/keep.py",
        ".venv/keep.py",
        "app/code.py",
    ):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# filler", encoding="utf-8")

    found = {p.relative_to(tmp_path).as_posix() for p in iter_project_files(tmp_path, "*.py")}
    assert found == {"app/code.py"}


def test_iter_project_files_honors_user_exclude_globs(tmp_path: Path) -> None:
    """[tool.azure-functions-doctor].exclude globs filter traversal results."""
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "auto.py").write_text("# gen", encoding="utf-8")
    (tmp_path / "manual.py").write_text("# manual", encoding="utf-8")

    token = set_extra_excludes(tmp_path, ["generated/**"])
    try:
        found = {p.name for p in iter_project_files(tmp_path, "*.py")}
    finally:
        reset_extra_excludes(token)

    assert found == {"manual.py"}


def test_dev_storage_skips_local_settings_template(tmp_path: Path) -> None:
    """local.settings.sample.json is a local template, not deployable infra."""
    (tmp_path / "local.settings.sample.json").write_text(
        '{"Values": {"AzureWebJobsStorage": "UseDevelopmentStorage=true"}}',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("azure-functions==1.25.0\n", encoding="utf-8")

    from azure_functions_doctor.handlers.registry import HandlerRegistry

    rule = cast(
        Rule,
        {
            "id": "test",
            "type": "dev_storage_connection",
            "required": False,
            "condition": {},
        },
    )
    registry = HandlerRegistry()
    result = registry.handle(rule, tmp_path)
    assert result["status"] == "pass"
    assert "No dev-storage emulator connection" in result["detail"]
