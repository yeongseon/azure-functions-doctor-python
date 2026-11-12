"""Tests for tools/audit_release_tags.py (read-only release-tag audit)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
from types import ModuleType
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PATH = _REPO_ROOT / "tools" / "audit_release_tags.py"
_spec = importlib.util.spec_from_file_location("audit_release_tags", _PATH)
assert _spec and _spec.loader
audit: ModuleType = importlib.util.module_from_spec(_spec)
# dataclasses resolves annotations through sys.modules.
import sys  # noqa: E402

sys.modules["audit_release_tags"] = audit
_spec.loader.exec_module(audit)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _commit(repo: Path, version: str, message: str) -> str:
    target = repo / "src" / "azure_functions_doctor" / "__init__.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def _audit(
    repo: Path,
    tag: str,
    *,
    honour: bool = False,
    exceptions: dict[str, Any] | None = None,
) -> Any:
    return audit.audit_tag(repo, tag, "main", honour_exceptions=honour, exceptions=exceptions)


def test_valid_release_tag_is_ok(repo: Path) -> None:
    _commit(repo, "1.2.3", "release")
    _git(repo, "tag", "v1.2.3")
    report = _audit(repo, "v1.2.3")
    assert report.status == "ok"
    assert report.source_version == "1.2.3"
    assert report.on_main is True


def test_version_mismatch_is_rejected(repo: Path) -> None:
    _commit(repo, "0.16.2", "release")
    _git(repo, "tag", "v0.16.4")
    report = _audit(repo, "v0.16.4")
    assert report.status == "FAIL"
    assert report.defects == ["version-mismatch"]
    assert "declares 0.16.2" in report.note


def test_tag_off_main_is_rejected(repo: Path) -> None:
    _commit(repo, "1.0.0", "base")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, "1.0.1", "side release")
    _git(repo, "tag", "v1.0.1")
    _git(repo, "checkout", "-q", "main")
    report = _audit(repo, "v1.0.1")
    assert report.defects == ["not-on-main"]
    assert report.status == "FAIL"


def test_missing_source_version_is_rejected(repo: Path) -> None:
    (repo / "README").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "no version")
    _git(repo, "tag", "v1.0.0")
    assert _audit(repo, "v1.0.0").defects == ["no-source-version"]


def test_pyproject_fallback_for_early_history(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "early")
    _git(repo, "tag", "v0.1.0")
    assert _audit(repo, "v0.1.0").status == "ok"


def test_action_ref_is_not_a_package_release(repo: Path) -> None:
    _commit(repo, "1.2.3", "release")
    _git(repo, "tag", "v1")
    report = _audit(repo, "v1")
    assert report.kind == "action-ref"
    assert report.status == "action-ref"
    assert report.defects == []


def test_unrecognized_tag_shape_fails(repo: Path) -> None:
    _commit(repo, "1.2.3", "release")
    _git(repo, "tag", "release-1.2.3")
    assert _audit(repo, "release-1.2.3").status == "FAIL"


def test_exception_is_pinned_to_commit_and_defects(repo: Path) -> None:
    sha = _commit(repo, "0.1.0", "early")
    _git(repo, "tag", "v0.1.1")
    registry = {"v0.1.1": audit.KnownException(sha, frozenset({"version-mismatch"}), "documented")}
    excepted = _audit(repo, "v0.1.1", honour=True, exceptions=registry)
    assert excepted.status == "exception"
    assert "documented" in excepted.note
    # Gate mode never honours exceptions.
    assert _audit(repo, "v0.1.1", honour=False, exceptions=registry).status == "FAIL"
    # A re-pointed tag no longer matches the registered commit.
    stale = {
        "v0.1.1": audit.KnownException("0" * 40, frozenset({"version-mismatch"}), "documented")
    }
    assert _audit(repo, "v0.1.1", honour=True, exceptions=stale).status == "FAIL"
    # An additional, unregistered defect is not hidden.
    narrow = {"v0.1.1": audit.KnownException(sha, frozenset({"not-on-main"}), "documented")}
    assert _audit(repo, "v0.1.1", honour=True, exceptions=narrow).status == "FAIL"


def test_unknown_tag_raises_git_error(repo: Path) -> None:
    _commit(repo, "1.0.0", "base")
    with pytest.raises(audit.GitError):
        _audit(repo, "v9.9.9")


def test_cli_gate_and_audit_modes(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _commit(repo, "1.0.0", "release")
    _git(repo, "tag", "v1.0.0")
    _commit(repo, "1.0.1", "release")
    _git(repo, "tag", "v1.0.2")
    base = ["--repo", str(repo), "--main-ref", "main"]

    assert audit.main(["--tag", "v1.0.0", *base]) == 0
    assert audit.main(["--tag", "v1.0.2", *base]) == 1
    assert audit.main(["--tag", "v1", *base]) == 2  # missing tag -> usage/git error
    assert audit.main(["--all", *base]) == 1
    out = capsys.readouterr().out
    assert "v1.0.2" in out and "FAIL" in out

    assert audit.main(["--all", "--json", *base]) == 1
    assert '"status": "FAIL"' in capsys.readouterr().out


def test_cli_gate_rejects_non_package_tag(repo: Path) -> None:
    _commit(repo, "1.0.0", "release")
    _git(repo, "tag", "v1")
    assert audit.main(["--tag", "v1", "--repo", str(repo), "--main-ref", "main"]) == 1


def test_list_tags_is_version_ordered(repo: Path) -> None:
    _commit(repo, "1.0.0", "release")
    for tag in ("v0.10.0", "v0.2.0", "v0.1.11", "v0.1.2"):
        _git(repo, "tag", tag)
    assert audit.list_tags(repo) == ["v0.1.2", "v0.1.11", "v0.2.0", "v0.10.0"]


def test_this_repository_tag_history_has_no_unregistered_defects() -> None:
    """Skips when the checkout has no tags/origin/main (e.g. shallow clones)."""
    try:
        tags = audit.list_tags(_REPO_ROOT)
        audit._git(_REPO_ROOT, "rev-parse", "--verify", "origin/main")
    except audit.GitError:
        pytest.skip("no git history available")
    if "v0.23.1" not in tags:
        pytest.skip("release tags not fetched")
    reports = [audit.audit_tag(_REPO_ROOT, t, "origin/main", honour_exceptions=True) for t in tags]
    assert [r.tag for r in reports if r.status == "FAIL"] == []
    assert {r.tag for r in reports if r.status == "exception"} == set(audit.KNOWN_EXCEPTIONS)


def test_publish_workflow_runs_the_tag_gate() -> None:
    lint_spec = importlib.util.spec_from_file_location(
        "lint_release_workflows", _REPO_ROOT / "tools" / "lint_release_workflows.py"
    )
    assert lint_spec and lint_spec.loader
    lint_mod = importlib.util.module_from_spec(lint_spec)
    lint_spec.loader.exec_module(lint_mod)
    assert lint_mod.check_tag_gate("run: noop", "x.yml")
    assert (
        lint_mod.check_tag_gate(
            'run: python tools/audit_release_tags.py --tag "$TAG_NAME"', "x.yml"
        )
        == []
    )
