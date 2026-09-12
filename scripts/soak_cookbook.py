"""Cookbook example soak (issue #428).

Runs the **published** azure-functions-doctor (PyPI install, not this repo)
over every cookbook example project and gates on:

1. Process health: exit code in {0, 1} and valid JSON for every project.
2. Contract: no absolute filesystem path in any finding location.
3. Regression: no project may produce a finding whose rule id is absent
   from the checked-in baseline (``scripts/cookbook_soak_baseline.json``).

The baseline is the FP alarm: a rule newly firing on the real-world corpus
(like the scan_before_spec false positive, #426) fails this gate until the
fix lands or the baseline is deliberately updated in the same PR.

Usage:
    python scripts/soak_cookbook.py <cookbook_examples_dir>            # gate
    python scripts/soak_cookbook.py <cookbook_examples_dir> --update   # rebaseline

Stdlib only — runs inside the CI job's venv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

BASELINE_PATH = Path(__file__).resolve().parent / "cookbook_soak_baseline.json"
DOCTOR_BIN = shutil.which("azure-functions-doctor")

# Machine-level rules depend on the HOST (func CLI, venv, interpreter), not the
# project: they legitimately differ between a developer laptop and the CI
# runner (first real run flagged every project with check_func_cli). The
# contract documents them as environment-dependent; exclude from the baseline
# comparison while still health/contract-checking their output.
MACHINE_LEVEL_RULES = frozenset(
    {
        "check_venv",
        "check_python_executable",
        "check_python_version",
        "check_python_runtime_lifecycle",
        "check_func_cli",
        "check_func_core_tools_version",
    }
)


def discover_projects(examples_dir: Path) -> list[Path]:
    """Every cookbook example directory that ships a function_app.py."""
    projects = []
    for child in sorted(examples_dir.rglob("function_app.py")):
        projects.append(child.parent)
    return sorted(set(projects))


def run_doctor(project: Path) -> tuple[int, dict[str, Any] | None, str]:
    """Run the published doctor over one project; return (rc, json, error)."""
    proc = subprocess.run(
        [DOCTOR_BIN, "doctor", "--path", str(project), "--profile", "full", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode not in (0, 1):
        return proc.returncode, None, proc.stderr[-400:]
    try:
        return proc.returncode, json.loads(proc.stdout), ""
    except ValueError as exc:
        return proc.returncode, None, f"invalid JSON: {exc}"


def findings(data: dict[str, Any]) -> list[tuple[str, str]]:
    """(rule_id, file-or-empty) for every warn/fail finding; absolute paths fail."""
    out: list[tuple[str, str]] = []
    for section in data.get("results", []):
        for item in section.get("items", []):
            if item.get("status") not in ("warn", "fail"):
                continue
            file_ref = str(item.get("file") or "")
            for location in item.get("locations") or []:
                file_ref = str(location.get("file") or file_ref or "")
            out.append((str(item.get("rule_id", "?")), file_ref))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("examples_dir", type=Path)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args()

    if DOCTOR_BIN is None:
        print("azure-functions-doctor not on PATH")
        return 2

    projects = discover_projects(args.examples_dir)
    if not projects:
        print(f"no example projects under {args.examples_dir}")
        return 2

    baseline: dict[str, list[str]] = {}
    if BASELINE_PATH.exists() and not args.update:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    failures: list[str] = []
    next_baseline: dict[str, list[str]] = {}
    for project in projects:
        name = project.relative_to(args.examples_dir.parent).as_posix()
        rc, data, error = run_doctor(project)
        if data is None:
            failures.append(f"{name}: rc={rc} {error}")
            continue
        found = findings(data)
        rule_ids = sorted({rule for rule, _file in found if rule not in MACHINE_LEVEL_RULES})
        next_baseline[name] = rule_ids
        for rule, file_ref in found:
            if file_ref.startswith("/"):
                failures.append(f"{name}: {rule} emitted an absolute path ({file_ref})")
        known = set(baseline.get(name, []))
        if not args.update:
            new = [rule for rule in rule_ids if rule not in known]
            if new:
                failures.append(f"{name}: NEW findings vs baseline: {new}")

    if args.update:
        BASELINE_PATH.write_text(
            json.dumps(dict(sorted(next_baseline.items())), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: {len(next_baseline)} projects -> {BASELINE_PATH}")
        return 0

    version = subprocess.run(
        [DOCTOR_BIN, "--version"], capture_output=True, text=True
    ).stdout.strip()
    print(f"soak: {len(projects)} projects, doctor {version}")
    if failures:
        print("SOAK FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        print("If the new findings are expected, rebaseline in the same PR:")
        print("  hatch run python scripts/soak_cookbook.py <cookbook>/examples --update")
        return 1
    print("SOAK PASSED: no crashes, no contract violations, no new findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
