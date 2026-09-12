from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Annotated, Mapping, Optional, cast

from rich.console import Console
from rich.text import Text
import typer

from azure_functions_doctor import __version__
from azure_functions_doctor.doctor import (
    FINDING_EVIDENCE_KEYS,
    FINDING_SCHEMA_VERSION,
    Doctor,
    _resolve_severity,
    _resolve_tier,
)
from azure_functions_doctor.logging_config import (
    get_logger,
    log_diagnostic_complete,
    log_diagnostic_start,
    setup_logging,
)
from azure_functions_doctor.target_resolver import (
    SUPPORTED_HOSTING_PLANS,
    SUPPORTED_PYTHON_VERSIONS,
    is_supported_python_for_plan,
    resolve_python_target,
)
from azure_functions_doctor.utils import (
    format_detail,
    format_freshness_line,
    format_status_icon,
)

cli = typer.Typer()
console = Console()
logger = get_logger(__name__)

SUPPORTED_TARGET_PYTHON_VERSIONS = SUPPORTED_PYTHON_VERSIONS
SUPPORTED_DEPLOYMENT_MODES = ("remote-build", "local", "local-prebuilt", "container")


def _version_callback(value: bool) -> None:
    """Print the installed version and exit (``--version``, issue #396)."""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@cli.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed azure-functions-doctor version and exit.",
    ),
) -> None:
    """Azure Functions Python runtime & deployment diagnostic engine."""


def _validate_inputs(
    path: str,
    format_type: str,
    output: Optional[Path],
    target_python: Optional[str] = None,
    deployment_mode: Optional[str] = None,
    hosting_plan: Optional[str] = None,
) -> None:
    """Validate CLI inputs before processing."""
    try:
        path_obj = Path(path).resolve()
    except (OSError, ValueError) as e:
        raise typer.BadParameter(f"Invalid path: {e}") from e

    if not path_obj.exists():
        raise typer.BadParameter(f"Path does not exist: {path}")

    if not path_obj.is_dir():
        raise typer.BadParameter(f"Path must be a directory: {path}")

    # Check read permissions
    if not os.access(path_obj, os.R_OK):
        raise typer.BadParameter(f"No read permission for path: {path}")

    # Validate format type
    if format_type not in ["table", "json", "sarif", "junit"]:
        raise typer.BadParameter(
            f"Invalid format: {format_type}. Must be 'table', 'json', 'sarif', or 'junit'"
        )

    # Validate output path
    if output:
        try:
            output_path = Path(output).resolve()
        except (OSError, ValueError) as e:
            raise typer.BadParameter(f"Invalid output path: {e}") from e

        if output_path.exists() and not output_path.is_file():
            raise typer.BadParameter(f"Output path exists but is not a file: {output}")

        # Check if parent directory exists or can be created
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise typer.BadParameter(f"Cannot create output directory: {e}") from e

        # Check write permissions
        if not os.access(output_path.parent, os.W_OK):
            raise typer.BadParameter(
                f"No write permission for output directory: {output_path.parent}"
            )

    if target_python is not None and target_python not in SUPPORTED_TARGET_PYTHON_VERSIONS:
        supported = ", ".join(SUPPORTED_TARGET_PYTHON_VERSIONS)
        raise typer.BadParameter(
            f"Invalid target Python: {target_python}. Supported values: {supported}"
        )

    if deployment_mode is not None and deployment_mode not in SUPPORTED_DEPLOYMENT_MODES:
        supported = ", ".join(SUPPORTED_DEPLOYMENT_MODES)
        raise typer.BadParameter(
            f"Invalid deployment mode: {deployment_mode}. Supported values: {supported}"
        )

    if hosting_plan is not None and hosting_plan not in SUPPORTED_HOSTING_PLANS:
        supported = ", ".join(SUPPORTED_HOSTING_PLANS)
        raise typer.BadParameter(
            f"Invalid hosting plan: {hosting_plan}. Supported values: {supported}"
        )

    if (
        target_python is not None
        and hosting_plan is not None
        and not is_supported_python_for_plan(target_python, hosting_plan)
    ):
        raise typer.BadParameter(
            f"Python {target_python} is not supported on the '{hosting_plan}' hosting plan. "
            "Linux Consumption caps at Python 3.12; use Flex Consumption, Premium, or "
            "Dedicated for newer runtimes."
        )


def _write_output(content: str, output: Optional[Path], label: str) -> None:
    if output:
        try:
            output.write_text(content, encoding="utf-8")
            console.print(
                f"[green]{format_status_icon('pass')} {label} output saved to:[/green] {output}"
            )
        except (OSError, IOError, PermissionError) as e:
            console.print(
                f"[red]{format_status_icon('fail')} Failed to write {label} output:[/red] {e}"
            )
            logger.error(f"Failed to write {label} output to {output}: {e}")
            raise typer.Exit(1) from e
    else:
        print(content)


@cli.command(name="doctor")
def doctor(
    path: str = ".",
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Show detailed hints for failed checks")
    ] = False,
    debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
    format: Annotated[
        str, typer.Option(help="Output format: 'table', 'json', 'sarif', or 'junit'")
    ] = "table",
    output: Annotated[
        Optional[Path], typer.Option(help="Optional path to save output result")
    ] = None,
    profile: Annotated[
        Optional[str],
        typer.Option(
            help=(
                "Rule profile: 'minimal' (required gating checks), 'deploy' "
                "(Azure runtime/hosting/deployment correctness), 'development' "
                "(local dev-environment checks), or 'full' (all rules)."
            ),
        ),
    ] = None,
    rules: Annotated[
        Optional[Path], typer.Option(help="Optional path to a custom rules file")
    ] = None,
    summary_json: Annotated[
        Optional[Path],
        typer.Option(
            "--summary-json",
            help="Write a JSON summary of counts (passed/warned/failed) to this path",
        ),
    ] = None,
    target_python: Annotated[
        Optional[str], typer.Option("--target-python", help="Override target Python runtime")
    ] = None,
    deployment_mode: Annotated[
        str,
        typer.Option(
            "--deployment-mode",
            help=(
                "Deployment mode: 'remote-build' (Azure builds from requirements.txt), "
                "'local' or 'local-prebuilt' (dependencies prebuilt/vendored locally), "
                "or 'container' (dependencies baked into a custom container image)."
            ),
        ),
    ] = "remote-build",
    hosting_plan: Annotated[
        Optional[str],
        typer.Option(
            "--hosting-plan",
            help=(
                "Target Azure hosting plan for Python-version validation: "
                "'linux-consumption' (caps at Python 3.12), 'flex-consumption', "
                "'premium', or 'dedicated'."
            ),
        ),
    ] = None,
) -> None:
    """
    Run diagnostics on an Azure Functions application.

    Args:
        path: Path to the Azure Functions app. Defaults to current directory.
        verbose: Show detailed hints for failed checks.
        debug: Enable debug logging to stderr.
        format: Output format: 'table', 'json', 'sarif', or 'junit'.
        output: Optional file path to save output result.
        profile: Optional rule profile ('minimal', 'deploy', 'development', or 'full').
        rules: Optional path to a custom rules file.
        summary_json: Path to write a JSON summary with passed/warned/failed counts.
        target_python: Optional target Python runtime override.
    """
    # Validate inputs before proceeding
    _validate_inputs(path, format, output, target_python, deployment_mode, hosting_plan)

    if rules is not None and not rules.exists():
        raise typer.BadParameter(f"Rules path does not exist: {rules}")

    # Configure logging based on CLI flags
    if debug:
        setup_logging(level="DEBUG", format_style="structured")
    else:
        # Use environment variable or default to WARNING
        setup_logging(level=None, format_style="simple")

    start_time = time.time()
    doctor = Doctor(
        path,
        profile=profile,
        rules_path=rules,
        target_python=target_python,
        deployment_mode=deployment_mode,
        hosting_plan=hosting_plan,
    )
    resolved_path = Path(path).resolve()
    report_properties = doctor.get_report_properties()

    # Log diagnostic start
    loaded_rules = doctor.load_rules()
    log_diagnostic_start(str(resolved_path), len(loaded_rules))
    results = doctor.run_all_checks(rules=loaded_rules)

    # Calculate execution metrics
    end_time = time.time()
    duration_ms = (end_time - start_time) * 1000

    # Count results for logging
    total_checks = sum(len(section["items"]) for section in results)
    passed_items = sum(
        1 for section in results for item in section["items"] if item.get("status") == "pass"
    )
    failed_items = sum(
        1 for section in results for item in section["items"] if item.get("status") == "fail"
    )
    # Note: handlers currently only return "pass"/"fail", not "error"
    errors = 0

    # Log diagnostic completion
    log_diagnostic_complete(total_checks, passed_items, failed_items, errors, duration_ms)

    # Pre-compute aggregated counts from normalized item['status'] values
    passed_count = 0
    warning_count = 0  # explicit 'warn' statuses
    fail_count = 0  # explicit 'fail' statuses
    skipped_count = 0  # explicit 'skip' statuses (check not applicable / prerequisite absent)
    for section in results:
        for item in section["items"]:
            s = item.get("status")
            if s == "pass":
                passed_count += 1
            elif s == "warn":
                warning_count += 1
            elif s == "fail":
                fail_count += 1
            elif s == "skip":
                skipped_count += 1
            else:
                warning_count += 1  # unknown treated as warning

    # Write summary JSON sidecar when --summary-json is specified (format-independent)
    if summary_json is not None:
        summary_data = {
            "passed": passed_count,
            "warned": warning_count,
            "failed": fail_count,
            "skipped": skipped_count,
        }
        try:
            summary_json.parent.mkdir(parents=True, exist_ok=True)
            summary_json.write_text(json.dumps(summary_data), encoding="utf-8")
        except (OSError, PermissionError) as exc:
            logger.warning(f"Failed to write summary JSON to {summary_json}: {exc}")

    if format == "json":
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        metadata = {
            "tool_version": __version__,
            "generated_at": generated_at,
            "target_path": str(Path(path).resolve()),
            **report_properties,
        }
        json_output = {
            "schema_version": FINDING_SCHEMA_VERSION,
            "metadata": metadata,
            "results": results,
        }
        _write_output(json.dumps(json_output, indent=2), output, "JSON")
        raise typer.Exit(1 if fail_count > 0 else 0)

    if format == "sarif":
        # rule_id is emitted on every result, so SARIF uses it directly

        # Build driver.rules from the full loaded ruleset
        driver_rules = []
        for rule in loaded_rules:
            driver_rule: dict[str, object] = {
                "id": rule.get("id", "unknown_rule"),
                "name": rule.get("label", "unknown_rule"),
                "shortDescription": {
                    "text": rule.get("description", rule.get("label", "unknown_rule"))
                },
                "properties": {
                    "category": rule.get("category", ""),
                    "required": rule.get("required", False),
                    "tier": _resolve_tier(rule),
                    "severity": _resolve_severity(rule),
                },
            }
            hint_url = rule.get("hint_url", "")
            if hint_url:
                driver_rule["helpUri"] = hint_url
            driver_rules.append(driver_rule)

        sarif_results = []
        # SARIF artifactLocation URIs paired with %SRCROOT% must be relative
        # references (SARIF 2.1.0 §3.4.4), so the scan root is normalized once
        # (#392): a relative --path (e.g. "services/api" in a monorepo) becomes
        # the repo-root prefix for every URI; an absolute --path cannot be
        # related to the runner's checkout root, so URIs stay scan-root-relative
        # and never leak filesystem paths into the report.
        scan_root_norm = path.replace("\\", "/").rstrip("/")
        scan_root_is_absolute = scan_root_norm.startswith("/") or (
            len(scan_root_norm) > 1 and scan_root_norm[1] == ":"
        )
        scan_prefix = ""
        if not scan_root_is_absolute and scan_root_norm not in ("", "."):
            scan_prefix = scan_root_norm + "/"

        def _physical_location_for(
            entry: Mapping[str, object],
        ) -> tuple[dict[str, object], str, object]:
            """Build one physicalLocation from an item or per-finding entry.

            Returns ``(physical_location, artifact_uri, loc_line)``. URIs are
            repo-root-relative per issue #392; entries may carry an absolute
            path defensively, which is rebased onto the scan root.
            """
            loc_file = entry.get("file")
            artifact_uri = ""
            loc_line: object = None
            if loc_file:
                artifact_uri = str(loc_file).replace("\\", "/")
                if Path(str(loc_file)).is_absolute():
                    try:
                        artifact_uri = str(Path(str(loc_file)).relative_to(Path(path))).replace(
                            "\\", "/"
                        )
                    except ValueError:
                        artifact_uri = Path(str(loc_file)).name
                if artifact_uri.startswith("./"):
                    artifact_uri = artifact_uri[2:]
                artifact_uri = scan_prefix + artifact_uri
                physical: dict[str, object] = {
                    "artifactLocation": {
                        "uri": artifact_uri,
                        "uriBaseId": "%SRCROOT%",
                    }
                }
                raw_line = entry.get("line")
                if isinstance(raw_line, int) and raw_line > 0:
                    loc_line = raw_line
                    region: dict[str, object] = {"startLine": raw_line}
                    raw_end = entry.get("end_line")
                    if isinstance(raw_end, int) and raw_end > 0:
                        region["endLine"] = raw_end
                    raw_col = entry.get("column")
                    if isinstance(raw_col, int) and raw_col > 0:
                        region["startColumn"] = raw_col
                    physical["region"] = region
                return physical, artifact_uri, loc_line
            # Rules without a file location point at the scan root in its
            # repo-root-relative form; absolute roots collapse to "." (#392).
            return (
                {
                    "artifactLocation": {
                        "uri": scan_prefix if scan_prefix else ".",
                        "uriBaseId": "%SRCROOT%",
                    }
                },
                scan_prefix if scan_prefix else ".",
                None,
            )

        for section in results:
            for item in section["items"]:
                status = item.get("status")
                # Skipped checks are not findings; exclude them from SARIF output.
                if status in ("pass", "skip"):
                    continue
                rule_id = item.get("rule_id") or item.get("label", "")
                level = "error" if status == "fail" else "warning"

                # One SARIF result per finding (issue #395): when a handler
                # supplies structured ``locations``, each entry becomes its
                # own result with its own region and message.
                item_map = cast(Mapping[str, object], item)
                raw_locations = item_map.get("locations")
                entries: list[tuple[Mapping[str, object], str]] = []
                if isinstance(raw_locations, list) and raw_locations:
                    for raw_entry in raw_locations:
                        if isinstance(raw_entry, dict):
                            entry_map = cast(Mapping[str, object], raw_entry)
                            per_message = str(entry_map.get("message") or item.get("value", ""))
                            entries.append((entry_map, per_message))
                if not entries:
                    entries = [(item_map, str(item.get("value", "")))]

                props: dict[str, object] = {}
                if item.get("hint"):
                    props["hint"] = item.get("hint", "")
                for key in FINDING_EVIDENCE_KEYS:
                    val = item_map.get(key)
                    if isinstance(val, str) and val:
                        props[key] = val
                analysis = item.get("analysis")
                if analysis:
                    props["analysis"] = analysis

                for entry, message_text in entries:
                    physical_location, artifact_uri, loc_line = _physical_location_for(entry)
                    # Stable fingerprint so Code Scanning can match alerts across
                    # runs even when lines shift (#392).
                    line_for_seed = loc_line if isinstance(loc_line, int) else 0
                    fingerprint_seed = f"{rule_id}:{artifact_uri}:{line_for_seed}"
                    sarif_result: dict[str, object] = {
                        "ruleId": rule_id,
                        "message": {"text": message_text},
                        "level": level,
                        "locations": [{"physicalLocation": physical_location}],
                        "partialFingerprints": {
                            "primaryLocationLineHash": hashlib.sha256(
                                fingerprint_seed.encode("utf-8")
                            ).hexdigest()
                        },
                    }
                    if props:
                        sarif_result["properties"] = props
                    sarif_results.append(sarif_result)

        sarif_output = {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "properties": report_properties,
                    "tool": {
                        "driver": {
                            "name": "azure-functions-doctor",
                            "version": __version__,
                            "informationUri": "https://github.com/yeongseon/azure-functions-doctor-python",
                            "rules": driver_rules,
                        }
                    },
                    "results": sarif_results,
                }
            ],
        }
        _write_output(json.dumps(sarif_output, indent=2), output, "SARIF")
        raise typer.Exit(1 if fail_count > 0 else 0)

    if format == "junit":
        import xml.etree.ElementTree as ET  # nosec B405

        tests = 0
        failures = 0
        skipped = 0
        suite = ET.Element(
            "testsuite",
            name="azure-functions-doctor",
            tests="0",
            failures="0",
            skipped="0",
            time=f"{duration_ms / 1000:.3f}",
        )

        for section in results:
            for item in section["items"]:
                tests += 1
                case = ET.SubElement(
                    suite, "testcase", classname=section["title"], name=item.get("label", "")
                )
                status = item.get("status")
                if status == "fail":
                    failures += 1
                    failure = ET.SubElement(case, "failure", message=item.get("value", ""))
                    failure.text = item.get("hint", "")
                elif status in ("warn", "skip"):
                    skipped += 1
                    skipped_el = ET.SubElement(case, "skipped", message=item.get("value", ""))
                    skipped_el.text = item.get("hint", "")

        suite.set("tests", str(tests))
        suite.set("failures", str(failures))
        suite.set("skipped", str(skipped))
        junit_output = ET.tostring(suite, encoding="utf-8", xml_declaration=True).decode("utf-8")
        _write_output(junit_output, output, "JUnit")
        raise typer.Exit(1 if fail_count > 0 else 0)

    # Note: Top header removed per UI change; programming model header intentionally omitted

    if debug:
        console.print("[dim]Debug logging enabled - check stderr for detailed logs[/dim]\n")

    # Table-format user-facing output (requested design)
    console.print("Azure Functions Doctor   ")
    console.print(f"Path: {resolved_path}")
    if target_python is not None:
        console.print(f"Target Python: {target_python} (override)")
    else:
        resolved_target, target_source = resolve_python_target(resolved_path)
        if target_source != "tool-runtime":
            console.print(f"Target Python: {resolved_target} ({target_source})")

    # Print each section with simple title and items
    for section in results:
        console.print()
        console.print(section["title"])

        for item in section["items"]:
            label = item.get("label", "")
            value = item.get("value", "")
            status = item.get("status", "pass")
            icon = format_status_icon(status)

            # Compose main line: [ICON] Label: value (status)
            line = Text.assemble((f"[{icon}] ", "bold"), (label, "dim"))
            if value:
                line.append(": ")
                line.append(format_detail(status, value))

            # append status in parentheses for clarity on UI when non-pass
            if status != "pass":
                line.append(f" ({status})", "italic dim")

            console.print(line)

            # Finding Contract v2 (issue #348): surface source-verified freshness
            # for date / compatibility findings that carry it.
            freshness = format_freshness_line(
                item.get("last_verified", ""), item.get("source_url", "")
            )
            if freshness:
                console.print(f"    [dim]{freshness}[/dim]")

            # show hint as 'fix:' only when verbose is enabled
            if status != "pass" and verbose:
                hint = item.get("hint", "")
                if hint:
                    prefix = "↪ "
                    console.print(f"    {prefix}fix: {hint}")

    # Use the precomputed counts from earlier for final output
    console.print()
    # Print Doctor summary at the bottom like the requested sample
    console.print("Doctor summary (to see all details, run azure-functions-doctor doctor -v):")
    # Use singular/plural simple form as in sample (error vs errors)
    # Summary now reflects canonical statuses: fails, warnings, passed
    w_label = "warning" if warning_count == 1 else "warnings"
    f_label = "fail" if fail_count == 1 else "fails"
    # 'passed' label remains same for singular/plural in current design
    console.print(f"  {fail_count} {f_label}, {warning_count} {w_label}, {passed_count} passed")
    if skipped_count:
        console.print(f"  {skipped_count} skipped")
    exit_code = 1 if fail_count > 0 else 0
    console.print(f"Exit code: {exit_code}")
    if exit_code != 0:
        raise typer.Exit(exit_code)


# Explicit command registration (test-friendly)
cli.command()(doctor)


# Deprecated console-script aliases. `azure-functions-doctor` is the canonical
# command; these wrappers emit a deprecation notice (to stderr, so structured
# stdout output such as JSON/SARIF stays clean) and then delegate to the CLI.
# Removal is targeted for the next major release (v1.0.0).
_CANONICAL_COMMAND = "azure-functions-doctor"


def _warn_deprecated_alias(alias: str) -> None:
    """Emit a deprecation notice for a legacy console-script alias."""
    Console(stderr=True).print(
        f"[yellow]Warning:[/yellow] the '{alias}' command is deprecated and will be "
        f"removed in a future release (targeted for v1.0.0). "
        f"Use '{_CANONICAL_COMMAND}' instead."
    )


# App-level options handled by the Typer callback itself; everything else
# given before the (only) `doctor` subcommand belongs to the doctor run.
_APP_LEVEL_FLAGS = {"--version", "--help", "-h"}


def normalize_argv(argv: list[str]) -> list[str]:
    """Insert the implicit ``doctor`` subcommand when it is omitted (#399).

    ``doctor`` is the only command, so the top level accepts the same options:
    ``azure-functions-doctor --path . --format json`` behaves identically to
    ``azure-functions-doctor doctor --path . --format json``. Pure function so
    the dispatch is unit-testable without spawning a process.
    """
    if not argv:
        return ["doctor"]
    first = argv[0]
    if first == "doctor":
        return list(argv)
    if first in _APP_LEVEL_FLAGS:
        return list(argv)
    if first.startswith("-"):
        return ["doctor", *argv]
    # Unknown bare word: let Typer surface its own "no such command" error.
    return list(argv)


def main() -> None:
    """Console-script entry point that tolerates the omitted subcommand."""
    import sys

    normalized = normalize_argv(sys.argv[1:])
    if normalized != sys.argv[1:]:
        sys.argv = [sys.argv[0], *normalized]
    cli()


def azure_functions_alias() -> None:
    """Deprecated alias entry point for the `azure-functions` console script."""
    _warn_deprecated_alias("azure-functions")
    cli()


def fdoctor_alias() -> None:
    """Deprecated alias entry point for the `fdoctor` console script."""
    _warn_deprecated_alias("fdoctor")
    cli()


if __name__ == "__main__":
    cli()
