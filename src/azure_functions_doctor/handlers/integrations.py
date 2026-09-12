"""Ecosystem-integration handlers (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

from pathlib import Path
from typing import Optional

from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    RuleContext,
    _collect_anonymous_auth_routes,
    _collect_openapi_version_mixing,
    _collect_routes_missing_validate_http_locations,
    _collect_scan_before_spec,
    _collect_unsupported_metadata_versions,
    _create_result,
    _project_activates_trace_context,
    _project_declares_openapi_dep,
    _project_declares_opentelemetry,
    _project_declares_validation_dep,
    _project_imports_langgraph,
    _rule_handler,
)


class IntegrationHandlers:
    """Ecosystem-integration handlers.

    Endpoint metadata, OpenAPI versioning, LangGraph auth, metadata versions,
    OTel activation.
    """

    @_rule_handler
    def _handle_endpoint_metadata(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when route handlers lack @validate_http in a validation-enabled project."""
        if not _project_declares_validation_dep(path):
            return _create_result(
                "skip", "azure-functions-validation not declared; endpoint metadata check skipped"
            )
        uncovered = _collect_routes_missing_validate_http_locations(path)
        if not uncovered:
            return _create_result("pass", "All route handlers expose endpoint metadata")
        detail = "\n".join(
            [
                "Route handlers missing @validate_http (no endpoint metadata):",
                *[f"- {label}" for label, _ln, _end, _col in uncovered[:10]],
                "",
                "Fix: add @validate_http so the route emits OpenAPI endpoint metadata.",
            ]
        )
        first_label, first_line, first_end_line, first_column = uncovered[0]
        first_file = first_label.rsplit(":", 1)[0]
        # One location per uncovered route so SARIF emits one result per
        # finding instead of collapsing onto the first route (issue #395).
        locations: list[dict[str, object]] = [
            {
                "file": label.rsplit(":", 1)[0],
                "line": line_no,
                "end_line": end_line,
                "column": column,
                "message": f"Route handler missing @validate_http (no endpoint metadata): {label}",
            }
            for label, line_no, end_line, column in uncovered[:10]
        ]
        return _create_result(
            "fail",
            detail,
            file=first_file,
            line=first_line,
            end_line=first_end_line,
            column=first_column,
            locations=locations,
        )

    @_rule_handler
    def _handle_openapi_version_mixing(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Detect when two or more OpenAPI versions (3.0/3.1/3.2) appear together."""
        signals = _collect_openapi_version_mixing(path)
        present = {version: sigs for version, sigs in signals.items() if sigs}
        if len(present) < 2:
            return _create_result("pass", "No OpenAPI version mixing detected")
        detail = "\n".join(
            [
                "Mixed OpenAPI version signals detected:",
                *[
                    f"- {version} signals: {', '.join(sorted(sigs))}"
                    for version, sigs in sorted(present.items())
                ],
                "",
                "Fix: standardise on a single OpenAPI version across the project.",
            ]
        )
        return _create_result("fail", detail)

    @_rule_handler
    def _handle_scan_before_spec(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Detect when the OpenAPI spec is built before endpoints are scanned."""
        if not _project_declares_openapi_dep(path):
            return _create_result(
                "skip",
                "azure-functions-openapi not declared; scan-before-spec check skipped",
            )
        condition = rule.get("condition", {}) or {}
        scan_names = set(
            condition.get("scan_names")
            or [
                "scan",
                "scan_endpoints",
                "scan_endpoint_metadata",
                "discover_endpoints",
                "register_functions",
                "register_blueprints",
            ]
        )
        spec_names = set(
            condition.get("spec_names")
            or [
                "build_spec",
                "build",
                "get_openapi_spec",
                "get_openapi_json",
                "get_openapi_yaml",
                "generate_openapi_spec",
                "generate_openapi_report",
                "generate_spec",
                "create_spec",
            ]
        )
        violations, located = _collect_scan_before_spec(path, scan_names, spec_names)
        if not violations:
            return _create_result("pass", "No spec-before-scan ordering issues detected")
        detail = "\n".join(
            [
                "OpenAPI spec built before endpoints were scanned:",
                *[f"- {loc}" for loc in violations[:10]],
                "",
                "Fix: call the endpoint scan/registration before building the spec.",
            ]
        )
        # The collector already knows the offending lines; pass them through so
        # SARIF findings land on the exact spec call (#394).
        locations = [
            {
                "file": label.rsplit(":", 1)[0],
                "line": lineno,
                "message": f"OpenAPI spec built before endpoints were scanned: {label}",
            }
            for label, lineno in located[:10]
            if label.rsplit(":", 1)[0] in {v.rsplit(":", 1)[0] for v in violations}
        ]
        first = located[0] if located else None
        return _create_result(
            "fail",
            detail,
            file=first[0].rsplit(":", 1)[0] if first else None,
            line=first[1] if first else None,
            locations=locations,
        )

    @_rule_handler
    def _handle_langgraph_anonymous_auth(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Detect when a LangGraph project exposes routes with anonymous auth."""
        if not _project_imports_langgraph(path):
            return _create_result("skip", "langgraph not imported; anonymous auth check skipped")
        condition = rule.get("condition", {}) or {}
        flag_missing = bool(condition.get("flag_missing_auth_level", False))
        flagged = _collect_anonymous_auth_routes(path, flag_missing)
        if not flagged:
            return _create_result("pass", "No anonymous-auth routes detected in LangGraph project")
        detail = "\n".join(
            [
                "Anonymous-auth routes detected in a LangGraph project:",
                *[f"- {loc}" for loc, _ln in flagged[:10]],
                "",
                "Fix: require authentication (e.g. AuthLevel.FUNCTION) for LangGraph routes.",
            ]
        )
        first = flagged[0] if flagged else None
        return _create_result(
            "fail",
            detail,
            file=first[0].rsplit(":", 1)[0] if first else None,
            line=first[1] if first else None,
            locations=[
                {
                    "file": lbl.rsplit(":", 1)[0],
                    "line": ln,
                    "message": f"Anonymous-auth route: {lbl}",
                }
                for lbl, ln in flagged[:10]
            ],
        )

    @_rule_handler
    def _handle_unsupported_metadata_version(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Detect when metadata declares an unsupported version."""
        condition = rule.get("condition", {}) or {}
        files = list(condition.get("files") or ["*.meta.json", "extensions.json"])
        fields = list(condition.get("fields") or ["metadataVersion", "metadata_version"])
        supported = list(condition.get("supported_versions") or [])
        if not supported:
            return _create_result(
                "skip", "No supported_versions configured; metadata version check skipped"
            )
        found = _collect_unsupported_metadata_versions(path, files, fields, supported)
        if not found:
            return _create_result("pass", "No unsupported metadata versions detected")
        detail = "\n".join(
            [
                "Unsupported metadata versions detected:",
                *[f"- {src} = {ver}" for src, ver in found[:10]],
                "",
                f"Fix: use a supported version ({', '.join(supported) or 'see docs'}).",
            ]
        )
        return _create_result("fail", detail)

    @_rule_handler
    def _handle_otel_activation(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when the project opts into logging OTel trace-context activation but
        does not declare an ``opentelemetry`` distribution.

        ``azure-functions-logging`` stays silent at runtime when activation is
        requested without OpenTelemetry installed, so doctor surfaces the mismatch.
        """
        activations = _project_activates_trace_context(path)
        if not activations:
            return _create_result(
                "skip", "No OTel trace-context activation requested; check skipped"
            )
        if _project_declares_opentelemetry(path):
            return _create_result(
                "pass", "Trace-context activation requested and opentelemetry is declared"
            )
        detail = "\n".join(
            [
                "Trace-context activation requested without an opentelemetry dependency:",
                *[f"- {loc}" for loc in activations[:10]],
                "",
                "Fix: install the azure-functions-logging[otel] extra (or an "
                "opentelemetry-* package), or disable activate_trace_context.",
            ]
        )

        def _activation_locations(labels: list[str]) -> list[dict[str, object]]:
            out: list[dict[str, object]] = []
            for loc in labels[:10]:
                file_part, _, line_part = loc.rpartition(":")
                out.append(
                    {
                        "file": file_part,
                        "line": int(line_part) if line_part.isdigit() else None,
                        "message": f"Trace-context activation without opentelemetry: {loc}",
                    }
                )
            return out

        first_loc = activations[0].rsplit(":", 1) if activations else None
        return _create_result(
            "fail",
            detail,
            file=first_loc[0] if first_loc else None,
            line=int(first_loc[1]) if first_loc and first_loc[1].isdigit() else None,
            locations=_activation_locations(activations),
        )
