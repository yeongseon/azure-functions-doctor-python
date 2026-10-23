import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    candidates: list[Path] = []
    try:
        result = subprocess.run(
            ["hatch", "env", "find"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            candidates.append(Path(result.stdout.strip()) / "bin/python")
    except OSError:
        candidates = []
    if os.environ.get("VIRTUAL_ENV"):
        candidates.append(Path(os.environ["VIRTUAL_ENV"]) / "bin/python")
    candidates.extend([Path(".venv/bin/python"), Path(sys.executable)])
    for python in candidates:
        if python.is_file():
            compatible = subprocess.run(
                [str(python), "-c", "import sys; raise SystemExit(sys.version_info < (3, 11))"],
                capture_output=True,
                check=False,
            )
            if compatible.returncode:
                continue
            command = [str(python.absolute()), "-m", "tools.verification", *sys.argv[1:]]
            environment = dict(
                os.environ,
                PATH=str(python.absolute().parent) + os.pathsep + os.environ.get("PATH", ""),
            )
            return subprocess.call(command, env=environment)
    print("Python >=3.11 required; development environment not created: run make install")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
