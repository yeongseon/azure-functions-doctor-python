"""Real Functions host smoke with private storage, ports and process groups."""

from __future__ import annotations

import base64
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from tools.verification_process import child, run


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_socket(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 30
    while process.poll() is None and time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError("Azurite exited or failed readiness")


def wait_host(process: subprocess.Popen[str], url: str) -> None:
    deadline = time.monotonic() + 90
    while process.poll() is None and time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200 and response.read() == b"doctor-host-smoke":
                    return
        except URLError:
            time.sleep(0.25)
    raise TimeoutError("Functions host exited or failed HTTP smoke readiness")


def host_smoke(directory: Path) -> int:
    directory = directory.resolve()
    root = Path.cwd()
    suite = ET.Element("testsuite", name="real-functions-host")
    case = ET.SubElement(suite, "testcase", name="diagnosed_app_serves_http")
    code = 1
    try:
        with tempfile.TemporaryDirectory(prefix="doctor-host-") as temporary, ExitStack() as stack:
            work = Path(temporary)
            for name in ("function_app.py", "host.json"):
                (work / name).write_bytes((root / "tests/host_smoke" / name).read_bytes())
            (work / "requirements.txt").write_text(f"-e {root}\nazure-functions\n")
            for tool in ("func", "azurite"):
                if run([tool, "--version"], directory / "logs" / f"{tool}-version.log", 20):
                    raise RuntimeError(f"Cannot determine {tool} version")
            code = run(
                [sys.executable, "-m", "venv", str(work / ".venv")],
                directory / "logs/venv.log",
            )
            if code:
                raise RuntimeError("Host environment creation failed")
            python = str(work / ".venv/bin/python")
            code = run(
                [python, "-m", "pip", "install", "-e", str(root), "azure-functions"],
                directory / "logs/install.log",
            )
            if code:
                raise RuntimeError("Host dependencies installation failed")
            code = run(
                [str(work / ".venv/bin/azure-functions-doctor"), "doctor", "--path", str(work)],
                directory / "logs/diagnostics.log",
            )
            if code:
                raise RuntimeError("Product diagnostics rejected the host app")
            blob, queue, table, port = (free_port() for _ in range(4))
            key = base64.b64encode(os.urandom(32)).decode()
            emulator = stack.enter_context(
                child(
                    [
                        "env",
                        f"AZURITE_ACCOUNTS=doctordev:{key}",
                        "azurite",
                        "--silent",
                        "--location",
                        str(work / "storage"),
                        "--blobPort",
                        str(blob),
                        "--queuePort",
                        str(queue),
                        "--tablePort",
                        str(table),
                    ],
                    directory / "logs/azurite.log",
                )
            )
            for service in (blob, queue, table):
                wait_socket(emulator, service)
            (work / "local.settings.json").write_text(
                json.dumps(
                    {
                        "IsEncrypted": False,
                        "Values": {
                            "FUNCTIONS_WORKER_RUNTIME": "python",
                            "AzureWebJobsStorage": (
                                f"DefaultEndpointsProtocol=http;AccountName=doctordev;AccountKey={key};"
                                f"BlobEndpoint=http://127.0.0.1:{blob}/doctordev;"
                                f"QueueEndpoint=http://127.0.0.1:{queue}/doctordev;"
                                f"TableEndpoint=http://127.0.0.1:{table}/doctordev;"
                            ),
                        },
                    }
                )
            )
            host = stack.enter_context(
                child(
                    [
                        "env",
                        f"PATH={work / '.venv/bin'}{os.pathsep}{os.environ.get('PATH', '')}",
                        "func",
                        "start",
                        "--python",
                        "--port",
                        str(port),
                    ],
                    directory / "logs/host.log",
                    work,
                )
            )
            wait_host(host, f"http://127.0.0.1:{port}/api/smoke")
        if re.search(
            r"0 functions (loaded|found)|No job functions found|"
            r"Executed 'Functions\..*' \(Failed|Worker failed",
            (directory / "logs/host.log").read_text(),
        ):
            raise RuntimeError("Functions host reported startup or invocation failure")
        code = 0
    except (OSError, RuntimeError, ValueError) as error:
        ET.SubElement(case, "failure").text = str(error)
        code = code or 1
    finally:
        destination = directory / "junit/junit.xml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(suite).write(destination, encoding="unicode")
    return code
