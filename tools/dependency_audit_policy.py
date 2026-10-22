"""Audit only an isolated wheel environment, with fail-closed redacted evidence."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
import subprocess
import sys

from tools.security_exceptions import parse_exceptions
from tools.security_report import (
    Check,
    EvidenceError,
    Finding,
    Status,
    identifier,
    load,
    mapping,
    sequence,
    text,
    write_report,
)


def classify_audit(raw: str, exit_status: int, *, policy_raw: str, today: date) -> Check:
    result = Check("pip-audit", ("resolved-runtime-wheel",), Status.TOOL_ERROR, exit_status)
    try:
        policy = load(policy_raw)
        if policy["schema_version"] != 1 or policy["blocking"] != "all-known-runtime":
            raise EvidenceError("unsupported policy")
        rules = parse_exceptions(policy["exceptions"], today)
        if any(r.file or r.line or not r.package or r.kind == "reviewed-static" for r in rules):
            raise EvidenceError("invalid dependency exception")
        dependencies = sequence(load(raw)["dependencies"])
        if exit_status not in {0, 1}:
            raise EvidenceError("tool crash")
        if not dependencies or any("skip_reason" in mapping(d) for d in dependencies):
            return replace(
                result, status=Status.INCOMPLETE, message="Empty or skipped audit scope."
            )
        findings: list[Finding] = []
        applied: set[str] = set()
        blocking = 0
        for dependency in dependencies:
            item = mapping(dependency)
            package = re.sub(r"[-_.]+", "-", identifier(item["name"]).lower())
            text(item["version"])
            for advisory in sequence(item["vulns"]):
                vuln = mapping(advisory)
                advisory_id = identifier(vuln["id"])
                severity = identifier(vuln.get("severity", "UNKNOWN"))
                findings.append(Finding(advisory_id, severity=severity, package=package))
                matches = [
                    r
                    for r in rules
                    if r.id == advisory_id
                    and re.sub(r"[-_.]+", "-", r.package.lower()) == package
                    and r.expires >= today
                ]
                if matches and (
                    matches[0].kind != "fix-not-available" or not sequence(vuln["fix_versions"])
                ):
                    applied.add(f"{package}:{advisory_id}")
                else:
                    blocking += 1
        if bool(findings) != (exit_status == 1):
            raise EvidenceError("exit status disagrees with findings")
        expired = sum(r.expires < today for r in rules)
        return replace(
            result,
            status=Status.FAIL if blocking or expired else Status.PASS,
            counts={
                "packages": len(dependencies),
                "findings": len(findings),
                "blocking": blocking,
                "expired_exceptions": expired,
                "stale_exceptions": len(rules) - len(applied),
            },
            findings=tuple(findings),
            exceptions_applied=tuple(sorted(applied)),
            message="All known runtime advisories block without a current applicable exception.",
        )
    except (ValueError, KeyError, TypeError):
        return replace(result, message="Invalid audit/tool/policy evidence; release blocked.")


def run_audit(site_packages: Path, policy: Path) -> Check:
    try:
        if not site_packages.is_dir() or not list(site_packages.glob("*.dist-info")):
            return Check(
                "pip-audit",
                ("resolved-runtime-wheel",),
                Status.INCOMPLETE,
                None,
                message="Candidate installation inventory missing.",
            )
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--path",
                str(site_packages),
                "--format",
                "json",
                "--desc",
                "off",
                "--progress-spinner",
                "off",
                "--timeout",
                "30",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        result = classify_audit(
            process.stdout,
            process.returncode,
            policy_raw=policy.read_text(encoding="utf-8"),
            today=date.today(),
        )
        return replace(result, tool_versions={"pip-audit": version("pip-audit")})
    except (OSError, subprocess.TimeoutExpired, PackageNotFoundError):
        return Check(
            "pip-audit",
            ("resolved-runtime-wheel",),
            Status.TOOL_ERROR,
            None,
            message="Audit execution failed; release blocked.",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument(
        "--policy", type=Path, default=Path("security/dependency-audit-policy.json")
    )
    parser.add_argument("--output", type=Path, default=Path("security-results"))
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    check = run_audit(args.site_packages, args.policy)
    if args.development:
        check = replace(check, name="pip-audit-development", scope=("runtime-and-development",))
    return write_report([check], args.output)


if __name__ == "__main__":
    raise SystemExit(main())
