from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

CHANGED_PATHS = Path(__file__).resolve().parents[1] / "tools" / "ci_changed_paths.sh"
FULL_MATRIX_OUTPUT = "docs_only=false\ndocs_changed=true\nfull_required=true\n"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def install_failing_git(tmp_path: Path, marker: Path) -> Path:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    real_git = shutil.which("git")
    assert real_git is not None
    (fake_bin / "git").write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = diff ]; then\n'
        f'  grep -Fxq \'full_required=true\' "$GITHUB_OUTPUT" && touch "{marker}"\n'
        "  exit 1\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n',
        encoding="utf-8",
    )
    (fake_bin / "git").chmod(0o755)
    return fake_bin


def test_fork_head_is_data_and_cannot_replace_the_trusted_classifier(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(work)], check=True, capture_output=True)
    git(work, "config", "user.name", "CI Test")
    git(work, "config", "user.email", "ci@example.invalid")
    (work / "tools").mkdir()
    (work / "tools" / "ci_classify_changes.sh").write_text(
        "#!/usr/bin/env bash\n"
        "printf 'docs_only=false\\ndocs_changed=true\\nfull_required=true\\n'\n",
        encoding="utf-8",
    )
    (work / "source.py").write_text("safe = True\n", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-m", "base")
    base = git(work, "rev-parse", "HEAD")
    git(work, "push", "origin", f"{base}:refs/heads/main")
    (work / "tools" / "ci_classify_changes.sh").write_text(
        "#!/usr/bin/env bash\n"
        "printf 'docs_only=true\\ndocs_changed=false\\nfull_required=false\\n'\n",
        encoding="utf-8",
    )
    (work / "source.py").write_text("safe = False\n", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-m", "malicious fork head")
    head = git(work, "rev-parse", "HEAD")
    git(work, "push", "origin", f"{head}:refs/pull/1/head")
    git(work, "checkout", "--detach", base)

    output = tmp_path / "output"
    env = os.environ | {
        "EVENT_NAME": "pull_request",
        "BASE_SHA": base,
        "HEAD_SHA": head,
        "PR_NUMBER": "1",
        "IS_FORK": "true",
        "BEFORE_SHA": "",
        "SHA": head,
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(
        ["bash", str(CHANGED_PATHS)], cwd=work, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "full_required=true" in output.read_text(encoding="utf-8")
    assert git(work, "rev-parse", "HEAD") == base


def test_force_push_range_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.name", "CI Test")
    git(repo, "config", "user.email", "ci@example.invalid")
    (repo / "tools").mkdir()
    (repo / "tools" / "ci_classify_changes.sh").write_text(
        "#!/usr/bin/env bash\n"
        "printf 'docs_only=true\\ndocs_changed=true\\nfull_required=false\\n'\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    before = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--orphan", "rewritten")
    git(repo, "rm", "-rf", ".")
    (repo / "README.md").write_text("rewritten\n", encoding="utf-8")
    (repo / "tools").mkdir(exist_ok=True)
    (repo / "tools" / "ci_classify_changes.sh").write_text("exit 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "force push")
    sha = git(repo, "rev-parse", "HEAD")
    output = tmp_path / "output"
    env = os.environ | {
        "EVENT_NAME": "push",
        "BASE_SHA": "",
        "HEAD_SHA": "",
        "PR_NUMBER": "",
        "IS_FORK": "false",
        "BEFORE_SHA": before,
        "SHA": sha,
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(
        ["bash", str(CHANGED_PATHS)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8").endswith("full_required=true\n")


def test_pull_request_git_diff_failure_keeps_full_matrix_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.name", "CI Test")
    git(repo, "config", "user.email", "ci@example.invalid")
    (repo / "tools").mkdir()
    (repo / "tools" / "ci_classify_changes.sh").write_text("exit 1\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("head\n", encoding="utf-8")
    git(repo, "commit", "-am", "head")
    head = git(repo, "rev-parse", "HEAD")
    output = tmp_path / "output"
    marker = tmp_path / "defaults-seen"
    fake_bin = install_failing_git(tmp_path, marker)
    env = os.environ | {
        "EVENT_NAME": "pull_request",
        "BASE_SHA": base,
        "HEAD_SHA": head,
        "PR_NUMBER": "1",
        "IS_FORK": "false",
        "BEFORE_SHA": "",
        "SHA": head,
        "GITHUB_OUTPUT": str(output),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", str(CHANGED_PATHS)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8") == FULL_MATRIX_OUTPUT
    assert marker.exists()


def test_push_git_diff_failure_keeps_full_matrix_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.name", "CI Test")
    git(repo, "config", "user.email", "ci@example.invalid")
    (repo / "tools").mkdir()
    (repo / "tools" / "ci_classify_changes.sh").write_text("exit 1\n", encoding="utf-8")
    (repo / "README.md").write_text("before\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "before")
    before = git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("after\n", encoding="utf-8")
    git(repo, "commit", "-am", "after")
    sha = git(repo, "rev-parse", "HEAD")
    output = tmp_path / "output"
    marker = tmp_path / "defaults-seen"
    fake_bin = install_failing_git(tmp_path, marker)
    env = os.environ | {
        "EVENT_NAME": "push",
        "BASE_SHA": "",
        "HEAD_SHA": "",
        "PR_NUMBER": "",
        "IS_FORK": "false",
        "BEFORE_SHA": before,
        "SHA": sha,
        "GITHUB_OUTPUT": str(output),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", str(CHANGED_PATHS)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8") == FULL_MATRIX_OUTPUT
    assert marker.exists()
