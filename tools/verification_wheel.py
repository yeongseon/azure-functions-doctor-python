"""Fresh candidate wheel identity and installed CLI smoke outside the checkout."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import sys
import sysconfig
import tempfile

from tools.verification_evidence import Summary, publish, save
from tools.verification_process import run


def main() -> int:
    directory = Path("test-results/wheel-smoke").resolve()
    if directory.exists():
        shutil.rmtree(directory)
    root = Path.cwd()
    expected = os.environ.get("E2E_EXPECTED_VERSION") or version("azure-functions-doctor")
    code, digest, reason = 1, "", ""
    try:
        with tempfile.TemporaryDirectory(prefix="doctor-wheel-") as temporary:
            work = Path(temporary)
            candidate = os.environ.get("VERIFICATION_WHEEL", "")
            if candidate:
                wheels = [Path(candidate).resolve()]
                code = 0
            else:
                code = run(
                    [
                        sys.executable,
                        "-m",
                        "build",
                        "--no-isolation",
                        "--outdir",
                        str(work / "dist"),
                    ],
                    directory / "logs/build.log",
                )
                wheels = list((work / "dist").glob("*.whl"))
            if code or len(wheels) != 1:
                raise RuntimeError("Expected one freshly built candidate wheel")
            digest = sha256(wheels[0].read_bytes()).hexdigest()
            code = run(
                [sys.executable, "-m", "venv", str(work / "venv")],
                directory / "logs/venv.log",
            )
            if code:
                raise RuntimeError("Wheel environment creation failed")
            python = str(work / "venv/bin/python")
            packages = (
                work
                / "venv/lib"
                / f"python{sys.version_info.major}.{sys.version_info.minor}"
                / "site-packages"
            )
            (packages / "verification-dependencies.pth").write_text(
                sysconfig.get_path("purelib") + "\n"
            )
            code = run(
                [python, "-m", "pip", "install", "--no-deps", "--no-index", str(wheels[0])],
                directory / "logs/install.log",
            )
            if code:
                raise RuntimeError("Candidate wheel installation failed")
            script = (
                "from pathlib import Path; from importlib.metadata import version; "
                "import azure_functions_doctor as a; "
                f"assert Path(a.__file__).resolve().is_relative_to(Path({str(work)!r})); "
                "assert version('azure-functions-doctor') == "
                f"{expected!r}; "
                "print('Installed candidate identity matches outside checkout')"
            )
            code = run([python, "-I", "-c", script], directory / "logs/identity.log", cwd=work)
            if code:
                raise RuntimeError("Installed candidate identity mismatch")
            code = run(
                [
                    "env",
                    "-u",
                    "PYTHONPATH",
                    str(work / "venv/bin/azure-functions-doctor"),
                    "doctor",
                    "--path",
                    str(root / "examples/v2/http-trigger"),
                    "--profile",
                    "minimal",
                    "--format",
                    "json",
                ],
                directory / "logs/cli.log",
                cwd=work,
            )
            json.loads((directory / "logs/cli.log").read_text())
    except (OSError, RuntimeError, ValueError) as error:
        code, reason = code or 1, str(error)
    summary = Summary(
        1,
        "wheel-smoke",
        ("installed-wheel", "doctor"),
        1,
        int(code == 0),
        int(code != 0),
        0,
        "PASS" if code == 0 else "FAIL",
        code,
    )
    publish(
        save(
            directory,
            replace(
                summary,
                reason=reason,
                candidate_version=expected,
                artifact_sha256=digest,
            ),
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
