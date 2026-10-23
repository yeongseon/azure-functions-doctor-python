from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

from tools.verification_evidence import collect, publish, save
from tools.verification_process import run


def main() -> int:
    directory = Path("test-results/cli-smoke")
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    suite = ET.Element("testsuite", name="static-example-cli")
    executable = shutil.which("azure-functions-doctor")
    if executable is None:
        print("Installed product CLI is required")
        return 2
    failed = False
    for fixture, expected in (("http-trigger", 0), ("broken-missing-host-json", 1)):
        case = ET.SubElement(suite, "testcase", name=fixture)
        code = run(
            [
                executable,
                "doctor",
                "--path",
                str(Path("examples/v2") / fixture),
                "--profile",
                "minimal",
                "--format",
                "json",
            ],
            directory / "logs" / f"{fixture}.log",
        )
        if code != expected:
            ET.SubElement(case, "failure").text = f"CLI exit {code} != expected {expected}"
            failed = True
        else:
            try:
                report = json.loads((directory / "logs" / f"{fixture}.log").read_text())
                if report["schema_version"] != "2.0" or report["metadata"]["gate_failed"] != bool(
                    expected
                ):
                    raise ValueError("CLI JSON contract mismatch")
            except (ValueError, KeyError) as error:
                ET.SubElement(case, "failure").text = str(error)
                failed = True
    ET.ElementTree(suite).write(directory / "junit.xml", encoding="unicode")
    summary = collect(directory, [executable, "doctor", "examples/v2"], int(failed))
    publish(save(directory, summary))
    return summary.exit_code


if __name__ == "__main__":
    sys.exit(main())
