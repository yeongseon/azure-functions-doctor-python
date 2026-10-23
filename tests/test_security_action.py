import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_action_path_is_not_interpreted_as_shell(tmp_path: Path) -> None:
    # Given a project path containing shell substitution and a harmless fake CLI.
    action = Path("action.yml").read_text(encoding="utf-8")
    block = action.split("      id: run-doctor\n", 1)[1]
    script = block.split("      run: |\n", 1)[1].split("\n    - name:", 1)[0]
    script = "\n".join(line[8:] for line in script.splitlines())
    marker = tmp_path / "PWNED"
    values = {
        "path": f"$(touch {marker})",
        "profile": "deploy",
        "format": "json",
        "output": str(tmp_path / "report.json"),
        "upload-sarif": "false",
        "fail-on-warn": "false",
    }
    for name, value in values.items():
        script = script.replace("${{ inputs." + name + " }}", value)
    fake = tmp_path / "azure-functions-doctor"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o700)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        **{"INPUT_" + name.upper().replace("-", "_"): value for name, value in values.items()},
    }
    # When GitHub's interpolated run script executes under bash.
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, timeout=10)
    # Then untrusted path syntax never becomes shell code.
    assert result.returncode == 0
    assert not marker.exists()


@pytest.mark.parametrize("payload", ["oversized", "symlink", "token", "counts"])
@pytest.mark.parametrize("output_path", ["report.json", "report\nPWNED=1"])
def test_action_summary_is_bounded_and_untrusted_counts_are_rejected(
    tmp_path: Path, payload: str, output_path: str
) -> None:
    # Given a real Bash action and a fake CLI replacing its private summary sidecar.
    action = Path("action.yml").read_text()
    block = action.split("      id: run-doctor\n", 1)[1]
    script = block.split("      run: |\n", 1)[1].split("\n    - name:", 1)[0]
    script = "\n".join(line[8:] for line in script.splitlines())
    fake = tmp_path / "azure-functions-doctor"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "p = pathlib.Path(sys.argv[sys.argv.index('--summary-json') + 1])\n"
        + {
            "oversized": "p.write_text(' ' * (5 * 1024 * 1024) + '{\"failed\":17}')\n",
            "symlink": "p.unlink(); p.symlink_to('/dev/zero')\n",
            "token": "p.write_text('CANARY_SECRET_ACTION')\n",
            "counts": 'p.write_text(\'{"failed":"CANARY_SECRET_ACTION\\\\nPWNED=1"}\')\n',
        }[payload]
    )
    fake.chmod(0o700)
    output = tmp_path / "outputs"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output),
        "INPUT_PATH": str(tmp_path),
        "INPUT_PROFILE": "deploy",
        "INPUT_FORMAT": "json",
        "INPUT_OUTPUT": output_path,
        "INPUT_UPLOAD_SARIF": "false",
        "INPUT_FAIL_ON_WARN": "false",
    }
    # When the action executes; Then sidecar/path content cannot inject outputs or leak.
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, timeout=10)
    assert result.returncode == 0
    text = output.read_text()
    assert "PWNED" not in text
    assert "CANARY_SECRET_ACTION" not in text + result.stdout.decode() + result.stderr.decode()
    assert "failed_count=unavailable\n" in text
    assert "summary_valid=false\n" in text
