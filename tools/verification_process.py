"""Bounded process-group ownership; raw output remains anonymous until redacted."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from types import FrameType

from tools.verification_evidence import redact


def terminate(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


@contextmanager
def child(
    command: list[str], log: Path, cwd: Path | None = None
) -> Iterator[subprocess.Popen[str]]:
    log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        with subprocess.Popen(
            command,
            cwd=cwd,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        ) as process:

            def interrupted(number: int, frame: FrameType | None) -> None:
                terminate(process)
                raise KeyboardInterrupt(number)

            previous = {
                sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)
            }
            try:
                yield process
            finally:
                terminate(process)
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                output.seek(0)
                text = redact(output.read())
                log.write_text(text, encoding="utf-8")
                print(text, end="")


def run(command: list[str], log: Path, timeout: float = 600, *, cwd: Path | None = None) -> int:
    try:
        with child(command, log, cwd) as process:
            try:
                code = process.wait(timeout=timeout)
                return code if code >= 0 else 128 - code
            except subprocess.TimeoutExpired:
                return 124
    except FileNotFoundError as error:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(redact(str(error)), encoding="utf-8")
        return 127
