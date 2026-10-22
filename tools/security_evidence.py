"""Execute the exact product inventory, including reviewed inline suppressions."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
import subprocess
import sys
import tokenize

from tools.security_exceptions import parse_exceptions
from tools.security_report import (
    Check,
    EvidenceError,
    Finding,
    Status,
    identifier,
    integer,
    load,
    mapping,
    sequence,
    text,
    write_report,
)

SCOPE = ("src", "examples", "demo", "scripts", "tools")
FILE_FLOOR = 30


def classify_bandit(raw: str, exit_status: int, *, floor: int = FILE_FLOOR) -> Check:
    result = Check("bandit", SCOPE, Status.TOOL_ERROR, exit_status)
    try:
        data = load(raw)
        metrics = mapping(data["metrics"])
        totals = mapping(metrics["_totals"])
        files = tuple(identifier(f.removeprefix("./")) for f in metrics if f != "_totals")
        findings: list[Finding] = []
        counts = {
            "files": len(files),
            "loc": integer(totals.get("loc", 0)),
            "errors": len(sequence(data["errors"])),
        }
        for entry in sequence(data["results"]):
            item = mapping(entry)
            severity, confidence = text(item["issue_severity"]), text(item["issue_confidence"])
            if severity not in {"LOW", "MEDIUM", "HIGH", "UNDEFINED"} or confidence not in {
                "LOW",
                "MEDIUM",
                "HIGH",
                "UNDEFINED",
            }:
                raise EvidenceError("invalid finding classification")
            findings.append(
                Finding(
                    identifier(item["test_id"]),
                    identifier(text(item["filename"]).removeprefix("./")),
                    integer(item["line_number"]),
                    severity,
                    confidence,
                )
            )
            for key in (f"severity.{severity}", f"confidence.{confidence}"):
                counts[key] = counts.get(key, 0) + 1
        suppressions = integer(totals.get("nosec", 0)) + integer(totals.get("skipped_tests", 0))
        result = replace(result, counts=counts, suppressions=suppressions, findings=tuple(findings))
        if exit_status not in {0, 1} or counts["errors"]:
            return replace(result, message="Scanner failure/error files; scan unusable.")
        if len(files) < floor or counts["loc"] == 0 or suppressions:
            return replace(
                result, status=Status.INCOMPLETE, message="Scan floor/skip policy failed."
            )
        if bool(findings) != (exit_status == 1):
            return replace(result, message="Scanner exit status disagrees with findings.")
        return replace(result, status=Status.FAIL if findings else Status.PASS)
    except (ValueError, KeyError, TypeError):
        return replace(result, message="Invalid Bandit JSON; raw diagnostics discarded.")


def apply_bandit_policy(check: Check, policy_raw: str, today: date) -> Check:
    if check.status not in {Status.PASS, Status.FAIL}:
        return check
    try:
        policy = load(policy_raw)
        if policy["schema_version"] != 1:
            raise EvidenceError("unsupported policy")
        rules = parse_exceptions(
            sequence(policy["exceptions"]) + sequence(policy.get("inline_suppressions", [])), today
        )
        if any(
            r.expires < today
            or not r.file
            or not r.line
            or r.package
            or r.kind != "reviewed-static"
            for r in rules
        ):
            return replace(
                check, status=Status.FAIL, message="Expired or invalid static exception."
            )
        applied: list[str] = []
        blocking = 0
        for finding in check.findings:
            if any(
                (r.id, r.file, r.line) == (finding.id, finding.file, finding.line) for r in rules
            ):
                applied.append(f"{finding.id}:{finding.file}:{finding.line}")
            else:
                blocking += 1
        return replace(
            check,
            status=Status.FAIL if blocking else Status.PASS,
            exceptions_applied=tuple(applied),
            counts={
                **check.counts,
                "blocking": blocking,
                "stale_exceptions": len(rules) - len(set(applied)),
            },
        )
    except (ValueError, KeyError, TypeError):
        return replace(check, status=Status.TOOL_ERROR, message="Invalid Bandit exception policy.")


def run_bandit() -> Check:
    try:
        process = subprocess.run(
            [sys.executable, "-m", "bandit", "-q", "-r", *SCOPE, "-f", "json", "--ignore-nosec"],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        result = classify_bandit(process.stdout, process.returncode)
        expected = {p.as_posix() for surface in SCOPE for p in Path(surface).rglob("*.py")}
        scanned = set(mapping(load(process.stdout)["metrics"])) - {"_totals"}
        if result.status != Status.TOOL_ERROR and (
            {p.removeprefix("./") for p in scanned} != expected
            or any(not Path(surface).is_dir() for surface in SCOPE)
        ):
            result = replace(
                result,
                status=Status.INCOMPLETE,
                message="Scanned inventory differs from declared surfaces.",
            )
        policy = Path("security/bandit-policy.json").read_text(encoding="utf-8")
        result = apply_bandit_policy(result, policy, date.today())
        rules = parse_exceptions(load(policy)["inline_suppressions"], date.today())
        observed: set[tuple[str, str, int]] = set()
        suppressions = 0
        for filename in expected:
            with tokenize.open(filename) as stream:
                for token in tokenize.generate_tokens(stream.readline):
                    if token.type != tokenize.COMMENT or "nosec" not in token.string:
                        continue
                    ids = re.findall(r"B\d{3}", token.string)
                    suppressions += 1
                    observed.update((rule_id, filename, token.start[0]) for rule_id in ids)
                    if not ids:
                        observed.add(("blanket", filename, token.start[0]))
        allowed = {(r.id, r.file, r.line) for r in rules}
        if observed != allowed and result.status != Status.TOOL_ERROR:
            result = replace(
                result,
                status=Status.INCOMPLETE,
                message="Inline suppression inventory differs from reviewed allow-list.",
            )
        return replace(
            result,
            suppressions=suppressions,
            tool_versions={"bandit": version("bandit")},
            counts={**result.counts, "inline_suppressions_reviewed": len(allowed)},
            message=result.message or "Existing inline suppressions audited with ignore-nosec.",
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
        ValueError,
        KeyError,
        TypeError,
        PackageNotFoundError,
        tokenize.TokenError,
        SyntaxError,
    ):
        return Check(
            "bandit",
            SCOPE,
            Status.TOOL_ERROR,
            None,
            message="Bandit execution/evidence collection failed.",
        )


def semgrep_evidence(outcome: str) -> Check:
    code: int | None
    match outcome:
        case "success":
            status, code = Status.PASS, 0
        case "failure":
            status, code = Status.TOOL_ERROR, 1
        case _:
            status, code = Status.INCOMPLETE, None
    return Check(
        "semgrep",
        ("action-outcome-only", "p/python"),
        status,
        code,
        tool_versions={"action": "713efdd345f3035192eaa63f56867b88e63e4e5d"},
        message="Action outcome only; finding count unknown; failures may include findings.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("bandit", "semgrep"))
    parser.add_argument("--outcome", default="")
    parser.add_argument("--output", type=Path, default=Path("security-results"))
    args = parser.parse_args()
    check = run_bandit() if args.check == "bandit" else semgrep_evidence(args.outcome)
    return write_report([check], args.output)


if __name__ == "__main__":
    raise SystemExit(main())
