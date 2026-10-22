import os
from pathlib import Path
import subprocess


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
