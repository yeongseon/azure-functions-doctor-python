"""Tests for pyproject-only dependency declaration support (issue #242).

Covers the ``dependency_manifest`` rule handler and the ``package_declared``
pyproject.toml fallback, plus the pure pyproject helper functions, so that
projects managing dependencies in ``pyproject.toml`` (without a
``requirements.txt``) are not reported as broken.
"""

from pathlib import Path
from typing import Any, cast

from azure_functions_doctor.handlers._helpers import (
    Rule,
    pyproject_declares_dependencies,
    pyproject_dependency_names,
)
from azure_functions_doctor.handlers.registry import HandlerRegistry

registry = HandlerRegistry()


def _write(path: Path, name: str, content: str) -> None:
    (path / name).write_text(content, encoding="utf-8")


def _status(
    rule_type: str,
    path: Path,
    condition: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    rule = cast(
        Rule,
        {"type": rule_type, "required": True, "condition": condition or {}},
    )
    return registry.handle(rule, path, cast(Any, context))["status"]


_PYPROJECT_WITH_DEPS = """\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "azure-functions>=1.17",
    "requests[security]>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]
"""

_PYPROJECT_NO_DEPS = """\
[project]
name = "demo"
version = "0.1.0"
"""


# ---------------------------------------------------------------------------
# pyproject helpers
# ---------------------------------------------------------------------------


def test_pyproject_dependency_names_collects_all_groups(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    names = pyproject_dependency_names(tmp_path)
    assert names == {"azure-functions", "requests", "pytest"}


def test_pyproject_dependency_names_missing_file(tmp_path: Path) -> None:
    assert pyproject_dependency_names(tmp_path) == set()


def test_pyproject_dependency_names_no_project_table(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[build-system]\nrequires = ['hatchling']\n")
    assert pyproject_dependency_names(tmp_path) == set()


def test_pyproject_dependency_names_invalid_toml(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "this is = = not toml [[[")
    assert pyproject_dependency_names(tmp_path) == set()


def test_pyproject_dependency_names_skips_unparseable_spec(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "d"\ndependencies = ["===bad===", "rich"]\n',
    )
    assert pyproject_dependency_names(tmp_path) == {"rich"}


def test_pyproject_declares_dependencies_true_and_false(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert pyproject_declares_dependencies(tmp_path) is True

    other = tmp_path / "empty"
    other.mkdir()
    _write(other, "pyproject.toml", _PYPROJECT_NO_DEPS)
    assert pyproject_declares_dependencies(other) is False


# ---------------------------------------------------------------------------
# dependency_manifest handler
# ---------------------------------------------------------------------------


def test_dependency_manifest_pass_with_requirements(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions\n")
    assert _status("dependency_manifest", tmp_path) == "pass"


def test_dependency_manifest_fail_pyproject_only_remote_build(tmp_path: Path) -> None:
    """Under the default remote build, pyproject-only is flagged (no requirements.txt)."""
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert _status("dependency_manifest", tmp_path) == "fail"


def test_dependency_manifest_pass_pyproject_only_local_mode(tmp_path: Path) -> None:
    """A declared local/prebuilt deployment accepts pyproject-only."""
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert (
        _status(
            "dependency_manifest",
            tmp_path,
            context={"deployment_mode": "local"},
        )
        == "pass"
    )


def test_dependency_manifest_pass_pyproject_only_vendored_packages(tmp_path: Path) -> None:
    """Vendored .python_packages implies a prebuilt deployment."""
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    (tmp_path / ".python_packages").mkdir()
    assert _status("dependency_manifest", tmp_path) == "pass"


def test_dependency_manifest_fail_when_neither(tmp_path: Path) -> None:
    assert _status("dependency_manifest", tmp_path) == "fail"


def test_dependency_manifest_fail_pyproject_without_deps(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", _PYPROJECT_NO_DEPS)
    assert _status("dependency_manifest", tmp_path) == "fail"


def test_dependency_manifest_optional_marks_detail(tmp_path: Path) -> None:
    rule = cast(
        Rule,
        {"type": "dependency_manifest", "required": False, "condition": {}},
    )
    result = registry.handle(rule, tmp_path)
    assert result["status"] == "fail"
    # Optional marking happens only during doctor.py's central aggregation
    # (where the resolved `gate` flag is known), not in the handler itself,
    # otherwise the central step duplicates the annotation (#597).
    assert "(optional)" not in result["detail"]


# ---------------------------------------------------------------------------
# package_declared pyproject fallback
# ---------------------------------------------------------------------------

_PKG_CONDITION = {"package": "azure-functions", "file": "requirements.txt"}


def test_package_declared_requirements_still_wins(tmp_path: Path) -> None:
    _write(tmp_path, "requirements.txt", "azure-functions\n")
    assert _status("package_declared", tmp_path, _PKG_CONDITION) == "pass"


def test_package_declared_pyproject_only_fail_remote_build(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert _status("package_declared", tmp_path, _PKG_CONDITION) == "fail"


def test_package_declared_pyproject_only_pass_local_mode(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert (
        _status(
            "package_declared",
            tmp_path,
            _PKG_CONDITION,
            context={"deployment_mode": "local"},
        )
        == "pass"
    )


def test_package_declared_requirements_lacks_it_fail_remote_build(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "requirements.txt", "rich\n")
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert _status("package_declared", tmp_path, _PKG_CONDITION) == "fail"


def test_package_declared_requirements_lacks_it_pass_local_mode(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "requirements.txt", "rich\n")
    _write(tmp_path, "pyproject.toml", _PYPROJECT_WITH_DEPS)
    assert (
        _status(
            "package_declared",
            tmp_path,
            _PKG_CONDITION,
            context={"deployment_mode": "local"},
        )
        == "pass"
    )


def test_package_declared_fail_when_missing_everywhere(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", _PYPROJECT_NO_DEPS)
    assert _status("package_declared", tmp_path, _PKG_CONDITION) == "fail"


def test_package_declared_fail_no_manifest_at_all(tmp_path: Path) -> None:
    assert _status("package_declared", tmp_path, _PKG_CONDITION) == "fail"
