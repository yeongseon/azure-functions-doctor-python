from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from tools.verification_environment import clean, doctor
from tools.verification_evidence import collect, publish, redact, report, save
from tools.verification_process import child, run


@pytest.mark.parametrize(
    ("cases", "code", "status"),
    [
        ("", 0, "INCOMPLETE"),
        ("", 5, "INCOMPLETE"),
        ("<testcase><skipped/></testcase>", 0, "INCOMPLETE"),
        ("<testcase/><testcase><skipped/></testcase>", 0, "INCOMPLETE"),
        ("<testcase><failure/></testcase>", 1, "FAIL"),
        ("<testcase/>", 0, "PASS"),
        ("<testcase/>", 124, "FAIL"),
    ],
)
def test_required_lane_classification(tmp_path: Path, cases: str, code: int, status: str) -> None:
    (tmp_path / "junit.xml").write_text(f"<testsuite>{cases}</testsuite>")
    summary = collect(tmp_path, ["pytest"], code)
    assert summary.status == status
    assert (summary.exit_code == 0) == (status == "PASS")


def test_azure_requires_remote_assertion_not_only_static_cli(tmp_path: Path) -> None:
    directory = tmp_path / "azure-e2e"
    directory.mkdir()
    (directory / "junit.xml").write_text(
        '<testsuite><testcase name="test_doctor_passes_on_example_project"/></testsuite>'
    )
    assert collect(directory, ["pytest"], 0).status == "INCOMPLETE"


@pytest.mark.parametrize(
    "secret",
    [
        "AccountKey=VERYSECRET;",
        "SharedAccessSignature=VERYSECRET;",
        "code=VERYSECRET&x=1",
        "x-functions-key: VERYSECRET",
        "Authorization: Bearer VERYSECRET",
        "password=VERYSECRET",
        "token=VERYSECRET",
        "AzureWebJobsStorage=VERYSECRET",
        "sas=VERYSECRET",
        "api_key=VERYSECRET",
        "DefaultEndpointsProtocol=https;AccountName=PRIVATE;AccountKey=VERYSECRET;",
        '"connection_string": "VERYSECRET"',
        "https://user:VERYSECRET@host/path",
    ],
)
def test_secret_canaries_removed_from_all_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], secret: str
) -> None:
    (tmp_path / "junit.xml").write_text(
        "<testsuite><testcase><system-out>"
        + secret.replace("&", "&amp;")
        + "</system-out></testcase></testsuite>"
    )
    (tmp_path / "runner.log").write_text(secret)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "job-summary"))
    publish(save(tmp_path, collect(tmp_path, ["pytest", secret], 0)))
    assert "VERYSECRET" not in capsys.readouterr().out
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "VERYSECRET" not in path.read_text()
    json.loads((tmp_path / "summary.json").read_text())


def test_environment_secrets_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_TOKEN", "opaque-sensitive-value")
    assert redact("opaque-sensitive-value") == "[REDACTED]"


def test_report_renders_saved_counts_without_execution(tmp_path: Path) -> None:
    directory = tmp_path / "test"
    directory.mkdir()
    (directory / "junit.xml").write_text("<testsuite><testcase/></testsuite>")
    (directory / "coverage.xml").write_text('<coverage line-rate="0.99"/>')
    save(directory, collect(directory, ["not-executable"], 0))
    assert report(tmp_path) == 0
    summary = json.loads((directory / "summary.json").read_text())
    assert (summary["selected"], summary["passed"], summary["coverage"]) == (1, 1, 0.99)


def test_doctor_requires_local_tools_but_not_live_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tools.verification_environment.importlib.util.find_spec", lambda _: True)
    monkeypatch.setattr(
        "tools.verification_environment.shutil.which",
        lambda tool: None if tool in {"func", "azurite"} else "/tools/" + tool,
    )
    assert doctor() == 0
    assert doctor(live=True) != 0


def test_doctor_is_read_only_when_required_tool_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification_environment.shutil.which", lambda _: None)
    assert doctor() != 0
    assert list(tmp_path.iterdir()) == []


def test_clean_preserves_sources_environments_and_shared_storage(tmp_path: Path) -> None:
    for name in (".venv", "src", "shared-azurite", "test-results", "dist", "build"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "keep").touch()
    clean(tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == [".venv", "shared-azurite", "src"]


def test_clean_unlinks_artifact_symlinks_without_following(tmp_path: Path) -> None:
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared/keep").touch()
    (tmp_path / "test-results").symlink_to(tmp_path / "shared", target_is_directory=True)
    clean(tmp_path)
    assert (tmp_path / "shared/keep").exists()


def test_process_failure_and_missing_executable_propagate(tmp_path: Path) -> None:
    assert run([sys.executable, "-c", "raise SystemExit(7)"], tmp_path / "log") == 7
    assert run(["/nonexistent/verification-command"], tmp_path / "missing") == 127


def test_interrupt_reaps_only_owned_process(tmp_path: Path) -> None:
    with (
        pytest.raises(KeyboardInterrupt),
        child([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "log") as process,
    ):
        raise KeyboardInterrupt
    assert process.poll() is not None


def test_timeout_reaps_and_redacts(tmp_path: Path) -> None:
    code = run(
        [sys.executable, "-u", "-c", "import time; print('password=VERYSECRET'); time.sleep(30)"],
        tmp_path / "log",
        0.2,
    )
    assert code == 124
    assert "VERYSECRET" not in (tmp_path / "log").read_text()
