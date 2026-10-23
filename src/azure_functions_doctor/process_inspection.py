"""Bounded capture for installed-tool metadata, never project commands."""

import os
import signal
import subprocess  # nosec B404
import sys
from typing import Final

MAX_PROCESS_OUTPUT_BYTES: Final = 64 * 1024
PROCESS_TIMEOUT_SECONDS: Final = 10


def read_tool_output(argv: list[str]) -> str:
    """Reap both direct children on failure, even when a descendant retains the pipe."""
    with subprocess.Popen(  # nosec B603
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
        bufsize=0,
    ) as process:
        if process.stdout is None:
            raise OSError("Tool output pipe is unavailable")

        def stop() -> None:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    process.kill()
            else:
                process.kill()
            process.wait()

        reader_code = (
            "import sys; "
            f"data = sys.stdin.buffer.read({MAX_PROCESS_OUTPUT_BYTES + 1}); "
            "sys.stdout.buffer.write(data)"
        )
        with subprocess.Popen(  # nosec B603
            [sys.executable, "-I", "-c", reader_code],
            stdin=process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as reader:
            process.stdout.close()
            try:
                output, _ = reader.communicate(timeout=PROCESS_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                stop()
                reader.kill()
                reader.communicate()
                raise
            if reader.returncode:
                stop()
                raise OSError("Tool output reader failed")
            if len(output) > MAX_PROCESS_OUTPUT_BYTES:
                stop()
                raise OSError("Inspection skips oversized tool output")
        try:
            code = process.wait(timeout=PROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            stop()
            raise
        if code:
            raise subprocess.CalledProcessError(code, argv)
        return output.decode("utf-8").strip()
