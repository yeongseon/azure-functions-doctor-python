"""Count actual reads/parses and retain deterministic findings for scan comparisons."""

import ast
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

from azure_functions_doctor.doctor import Doctor
from azure_functions_doctor.inspection import _read_text


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    for profile in ("minimal", "full"):
        cache_scope = (
            patch("azure_functions_doctor.doctor.source_cache", nullcontext)
            if os.environ.get("DOCTOR_UNCACHED") == "1"
            else nullcontext()
        )
        with (
            cache_scope,
            patch("ast.parse", wraps=ast.parse) as parses,
            patch("azure_functions_doctor.inspection._read_text", wraps=_read_text) as reads,
        ):
            start = perf_counter()
            doctor = Doctor(str(project), profile=profile)
            results = doctor.run_all_checks()
            elapsed = perf_counter() - start
        counts = {"reads": reads.call_count, "parses": parses.call_count}
        digest = hashlib.sha256(json.dumps(results, sort_keys=True).encode()).hexdigest()
        print(
            json.dumps(
                {
                    "profile": profile,
                    "counts": counts,
                    "seconds": elapsed,
                    "findings_sha256": digest,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
