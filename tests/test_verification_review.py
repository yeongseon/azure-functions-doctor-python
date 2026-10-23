import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.verification_evidence import Summary, redact, save
from tools.verification_host import wait_host


@pytest.mark.parametrize(
    "text",
    [
        '{"Authorization": "Bearer CANARY_secret"}',
        "{'Authorization': 'Bearer CANARY_secret'}",
        "Proxy-Authorization: Basic CANARY_secret",
        '{"password": "alpha CANARY_secret beta"}',
        '{"token": "with \\"escaped\\" CANARY_secret"}',
        "connection_string=Endpoint=sb://ns/;SharedAccessKeyName=Root;SharedAccessKey=CANARY_secret",
        "InstrumentationKey=CANARY_secret;IngestionEndpoint=https://x/",
        "DefaultEndpointsProtocol=https;AccountName=a;AccountKey=CANARY_secret;EndpointSuffix=x",
        "https://user:CANARY_secret@example.test/path",
        "https://CANARY_secret@example.test/path",
        "GET /api?code=CANARY_secret&sig=CANARY_secret&x-functions-key=CANARY_secret",
        '<failure message="Authorization: Bearer CANARY_secret">x</failure>',
    ],
)
def test_credential_shapes_are_consumed_whole(text: str) -> None:
    assert "CANARY_secret" not in redact(text)


def test_save_preserves_structured_and_binary_evidence(tmp_path: Path) -> None:
    png = b"\x89PNG\xff\x00"
    (tmp_path / "chart.png").write_bytes(png)
    (tmp_path / "extra.json").write_text(
        '{"password":123,"header":"Authorization: Bearer CANARY_secret"}'
    )
    outside = tmp_path.parent / f"{tmp_path.name}-outside.log"
    outside.write_text("password=CANARY_outside")
    (tmp_path / "link.log").symlink_to(outside)
    save(
        tmp_path,
        Summary(1, "test", ('Authorization: "Bearer CANARY_secret"',), 1, 1, 0, 0, "PASS", 0),
    )
    assert "CANARY_secret" not in (tmp_path / "summary.json").read_text()
    assert json.loads((tmp_path / "extra.json").read_text())["password"] == 123
    assert "CANARY_secret" not in (tmp_path / "extra.json").read_text()
    assert (tmp_path / "chart.png").read_bytes() == png
    assert outside.read_text() == "password=CANARY_outside"


def test_known_secret_replaced_before_partial_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_API_TOKEN", 'prefix;CANARY_secret "quoted" value')
    assert "CANARY_secret" not in redact(json.dumps({"x": 'prefix;CANARY_secret "quoted" value'}))


@pytest.mark.parametrize(
    "text", ['{"Authorization":"Bearer secret","ok":true}', '{"password":"alpha beta","n":1}']
)
def test_redaction_keeps_json_valid(text: str) -> None:
    assert json.loads(redact(text))


def test_parent_candidate_is_preserved_when_installed_in_child(tmp_path: Path) -> None:
    from zipfile import ZipFile

    wheel = tmp_path / "review_candidate-9999.0-py3-none-any.whl"
    metadata = "review_candidate-9999.0.dist-info"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("review_candidate.py", "VALUE = 1\n")
        archive.writestr(
            f"{metadata}/METADATA",
            "Metadata-Version: 2.1\nName: review-candidate\nVersion: 9999.0\n",
        )
        archive.writestr(
            f"{metadata}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        )
        archive.writestr(f"{metadata}/RECORD", "")
    parent = tmp_path / "parent"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(parent)], check=True)
    python = parent / "bin/python"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "--python",
            str(python),
            "install",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        check=True,
        capture_output=True,
    )
    parent_packages = (
        parent
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    original = (parent_packages / metadata / "METADATA").read_bytes()
    child = tmp_path / "child"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(child)], check=True)
    packages = (
        child / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    )
    (packages / "parent.pth").write_text(str(parent_packages) + "\n")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "--python",
            str(child / "bin/python"),
            "install",
            "--ignore-installed",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        check=True,
        capture_output=True,
    )
    assert (packages / metadata / "METADATA").read_bytes() == original
    assert (parent_packages / metadata / "METADATA").read_bytes() == original


def test_host_timeout_is_retried_before_success() -> None:
    process = MagicMock()
    process.poll.return_value = None
    response = MagicMock()
    response.__enter__.return_value.status = 200
    response.__enter__.return_value.read.return_value = b"doctor-host-smoke"
    with (
        patch("tools.verification_host.urlopen", side_effect=[TimeoutError(), response]) as request,
        patch("tools.verification_host.time.sleep"),
    ):
        wait_host(process, "http://127.0.0.1/smoke")
    assert request.call_count == 2


def test_quality_failure_retains_log_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.verification import focused

    monkeypatch.chdir(tmp_path)
    code = focused("check", [sys.executable, "-c", "print('quality failed'); raise SystemExit(7)"])
    assert code == 7
    result = json.loads((tmp_path / "test-results/check/summary.json").read_text())
    assert result["status"] == "FAIL"
    assert "quality failed" in (tmp_path / "test-results/check/logs/runner.log").read_text()


@pytest.mark.parametrize("target", ["doctor", "report", "clean"])
def test_maintenance_never_provisions_hatch(tmp_path: Path, target: str) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["make", "-n", target], cwd=root, capture_output=True, text=True)
    assert "hatch run" not in result.stdout


def test_fresh_maintenance_creates_no_hatch_environment(tmp_path: Path) -> None:
    import os
    import shutil

    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "tools", tmp_path / "tools")
    shutil.copyfile(root / "Makefile", tmp_path / "Makefile")
    environment = dict(os.environ, HATCH_DATA_DIR=str(tmp_path / "hatch-data"))
    environment.pop("CI", None)
    for target in ("doctor", "report", "clean"):
        result = subprocess.run(
            ["make", target], cwd=tmp_path, env=environment, capture_output=True, text=True
        )
        if target == "doctor":
            assert result.returncode != 0
            assert "development environment not created: run make install" in result.stdout
    assert not (tmp_path / "hatch-data/env").exists()


def test_check_make_target_saves_failure_evidence(tmp_path: Path) -> None:
    import shutil

    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "tools", tmp_path / "tools")
    makefile = (
        (root / "Makefile")
        .read_text()
        .replace("check-quality: style typecheck security lint-workflows", "check-quality:")
    )
    makefile = makefile.replace(
        "\t@$(RUN) scripts/lint_mermaid.py",
        "\t@$(RUN) -c \"print('lint failed'); raise SystemExit(9)\"",
    )
    (tmp_path / "Makefile").write_text(makefile)
    result = subprocess.run(
        ["make", "check", "CI=true", f"PYTHON={sys.executable}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    summary = json.loads((tmp_path / "test-results/check/summary.json").read_text())
    assert summary["status"] == "FAIL"
    assert "lint failed" in (tmp_path / "test-results/check/logs/runner.log").read_text()
