"""Generic structural handlers (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import List, Optional

from packaging.version import InvalidVersion
from packaging.version import parse as parse_version

from azure_functions_doctor.handlers._helpers import (
    _HOST_JSON_MISSING,
    _PYTHON_CANDIDATES,
    HandlerResult,
    Rule,
    RuleContext,
    _create_result,
    _handle_specific_exceptions,
    _iter_project_py_contents,
    _read_project_python_file,
    _resolve_host_json_path,
    _resolve_host_json_pointer,
    _rule_handler,
    _source_contains_ast,
    iter_project_files,
    logger,
    parse_compare_version,
    parse_source_code,
    parse_target,
)
from azure_functions_doctor.target_resolver import (
    SUPPORTED_PYTHON_VERSIONS,
    is_supported_python_target,
    resolve_python_target,
    resolve_target_value,
)


class GenericHandlers:
    """Generic structural handlers: version comparison, path/file/env/executable detection."""

    @_rule_handler
    def _handle_compare_version(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle version comparison checks."""
        condition = rule.get("condition", {}) or {}
        params = parse_compare_version(condition)
        if params is None:
            return _create_result("fail", "Missing condition fields for compare_version")
        target, operator, value = params

        if target == "python":
            target_python = context.get("target_python") if context is not None else None
            current_version, source = resolve_python_target(path, override=target_python)
            tool_runtime = (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )
            current = parse_version(current_version)
            expected = parse_version(str(value))
            operator_passed = {
                ">=": current >= expected,
                "<=": current <= expected,
                "==": current == expected,
                ">": current > expected,
                "<": current < expected,
            }.get(operator, False)
            supported = is_supported_python_target(current_version)
            passed = operator_passed and supported
            supported_range = f"{SUPPORTED_PYTHON_VERSIONS[0]}\u2013{SUPPORTED_PYTHON_VERSIONS[-1]}"
            if source == "override":
                detail = (
                    f"Target Python: {current_version} (override) "
                    f"\u2014 Tool runtime: {tool_runtime}"
                )
            elif source == "tool-runtime":
                detail = f"Python {current_version} (tool runtime, {operator}{value})"
            else:
                detail = (
                    f"Target Python: {current_version} ({source}, {operator}{value}) "
                    f"\u2014 Tool runtime: {tool_runtime}"
                )
            if not supported:
                detail += (
                    f" \u2014 unsupported target; Azure Functions supports Python {supported_range}"
                )
            return _create_result(
                "pass" if passed else "fail",
                detail,
            )

        if target == "func_core_tools":
            raw = resolve_target_value("func_core_tools")
            if raw in ("not_installed", "timeout", "unknown_error") or raw.startswith("error_"):
                return _create_result("fail", f"func: {raw}")
            try:
                current = parse_version(raw)
            except InvalidVersion:
                return _create_result("fail", f"func version unparseable: {raw}")
            expected = parse_version(str(value))
            passed = {
                ">=": current >= expected,
                "<=": current <= expected,
                "==": current == expected,
                ">": current > expected,
                "<": current < expected,
            }.get(operator, False)
            return _create_result(
                "pass" if passed else "fail",
                f"func {raw} ({operator}{value})",
            )

        return _create_result("fail", f"Unknown target for version comparison: {target}")

    @_rule_handler
    def _handle_env_var_exists(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle environment variable existence checks."""
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition)

        if not target:
            return _create_result("fail", "Missing environment variable name")

        exists = os.getenv(target) is not None
        return _create_result(
            "pass" if exists else "fail",
            f"{target} is {'set' if exists else 'not set'}",
        )

    @_rule_handler
    def _handle_path_exists(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle path existence checks."""
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition)

        if not target:
            return _create_result("fail", "Missing target path")

        if target == "sys.executable":
            if not sys.executable:
                return _create_result("fail", "sys.executable is empty")
            resolved_path = Path(sys.executable)
        else:
            resolved_path = path / target

        exists = resolved_path.exists()
        detail = f"{resolved_path} {'exists' if exists else 'missing'}"
        if not exists and not rule.get("required", True):
            detail += " (optional)"
        return _create_result("pass" if exists else "fail", detail)

    @_rule_handler
    def _handle_file_exists(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle file existence checks."""
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition)

        if not target:
            return _create_result("fail", "Missing file path")
        file_path = path / target
        rel_target = target.replace("\\", "/")
        exists = file_path.is_file()
        detail = f"{file_path} {'exists' if exists else 'not found'}"
        if not exists and not rule.get("required", True):
            detail += " (optional)"
        return _create_result("pass" if exists else "fail", detail, file=rel_target)

    @_rule_handler
    def _handle_conditional_exists(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle host.json checks that only matter when a related feature is detected."""
        durable_keywords = [
            "durable",
            "DurableOrchestrationContext",
            "durable_functions",
            "orchestrator",
        ]
        uses_durable = False

        try:
            for py_file in iter_project_files(path, "*.py"):
                content = _read_project_python_file(py_file)
                if content is None:
                    continue
                lowered = content.lower()
                if any(k in lowered for k in durable_keywords):
                    uses_durable = True
                    break
        except Exception as exc:
            return _handle_specific_exceptions("scanning for durable usage", exc)

        if not uses_durable:
            return _create_result("skip", "No Durable Functions usage detected; check skipped")

        condition = rule.get("condition", {}) or {}
        jsonpath = condition.get("jsonpath")

        if not jsonpath:
            return _create_result(
                "fail",
                "Missing jsonpath in condition for conditional_exists check",
            )

        if not isinstance(jsonpath, str):
            return _create_result("fail", "jsonpath must be a string for conditional_exists check")

        host_path = path / "host.json"
        if not host_path.exists():
            return _create_result("fail", "host.json missing (durable usage)")

        try:
            host_data = json.loads(host_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return _handle_specific_exceptions("reading host.json", exc)

        if _resolve_host_json_path(host_data, jsonpath) is _HOST_JSON_MISSING:
            return _create_result(
                "fail",
                f"Required host.json property '{jsonpath}' not found",
            )

        return _create_result("pass", f"host.json contains '{jsonpath}'")

    @_rule_handler
    def _handle_callable_detection(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Detect ASGI/WSGI callable exposure in source files (basic heuristics).

        A plain decorator-based ``FunctionApp`` project has no ASGI/WSGI app and
        should not be warned, so the check **skips** when there is no framework
        signal at all. When a framework is present but its callable is not wired
        into Azure Functions it returns ``fail`` (surfaced as a warning by the
        doctor only because this rule is optional); a correctly exposed callable
        passes.
        """
        # Azure Functions wiring that actually exposes an ASGI/WSGI callable.
        exposure_patterns = [
            r"\bAsgiFunctionApp\s*\(",
            r"\bWsgiFunctionApp\s*\(",
            r"\bAsgiMiddleware\s*\(",
            r"\bWsgiMiddleware\s*\(",
        ]
        # Presence of an ASGI/WSGI framework (import or instantiation).
        framework_patterns = [
            r"\bFastAPI\s*\(|\bStarlette\s*\(|\bFlask\s*\(|\bQuart\s*\(",
            r"\b(?:import|from)\s+(?:fastapi|starlette|flask|quart)\b",
            r"ASGIApp|WSGIApp|asgi_app|wsgi_app",
        ]

        exposure_hits: List[str] = []
        framework_hits: List[str] = []
        try:
            for py_file in iter_project_files(path, "*.py"):
                content = _read_project_python_file(py_file)
                if content is None:
                    continue
                rel = py_file.relative_to(path)
                for pat in exposure_patterns:
                    if re.search(pat, content):
                        exposure_hits.append(f"{rel}:{pat}")
                        break
                for pat in framework_patterns:
                    if re.search(pat, content):
                        framework_hits.append(f"{rel}:{pat}")
                        break
        except Exception as exc:
            return _handle_specific_exceptions("scanning for ASGI/WSGI callables", exc)

        if exposure_hits:
            return _create_result(
                "pass", f"Detected ASGI/WSGI callable exposure: {exposure_hits[:3]}"
            )

        if framework_hits:
            return _create_result(
                "fail",
                "ASGI/WSGI framework detected but no callable is exposed via "
                "AsgiFunctionApp/WsgiFunctionApp (or AsgiMiddleware/WsgiMiddleware); "
                f"wire it into Azure Functions: {framework_hits[:3]}",
            )

        return _create_result(
            "skip",
            "No ASGI/WSGI framework detected; plain FunctionApp project.",
        )

    # --- adapters / additional handlers ---

    @_rule_handler
    def _handle_executable_exists(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check if an executable is available on PATH."""
        condition = rule.get("condition", {}) or {}
        target = parse_target(condition)
        if not target:
            return _create_result("fail", "Missing 'target' for executable_exists")
        # Use candidate map for symmetric fallback
        candidates = _PYTHON_CANDIDATES.get(target, [target])
        found = any(shutil.which(c) is not None for c in candidates)
        if found:
            # Concise style: "<name> detected"
            return _create_result("pass", f"{target} detected")
        return _create_result("fail", f"{target} not found")

    @_rule_handler
    def _handle_any_of_exists(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Check if any of a list of targets exist (env vars, host.json keys, files)."""
        condition = rule.get("condition", {}) or {}
        targets = condition.get("targets", [])
        if not targets or not isinstance(targets, list):
            return _create_result("fail", "Missing 'targets' list for any_of_exists")

        for t in targets:
            if isinstance(t, str) and t.startswith("host.json:"):
                key = t.split("host.json:", 1)[1].lstrip(".")
                host_path = path / "host.json"
                if host_path.exists():
                    try:
                        data = json.loads(host_path.read_text(encoding="utf-8"))
                        node = _resolve_host_json_pointer(data, key.split("."))
                        if node is not _HOST_JSON_MISSING and node is not None:
                            return _create_result("pass", f"host.json:{key} present")
                    except json.JSONDecodeError as exc:
                        logger.debug(f"Skip invalid host.json while checking {key}: {exc}")
            else:
                # env var
                if os.getenv(str(t)) is not None:
                    return _create_result("pass", f"env:{t} set")
                # file path
                candidate = path / str(t)
                if candidate.exists():
                    return _create_result("pass", f"path:{candidate.name} present")
        # Shorter failure detail for concise output integration
        return _create_result("fail", "Targets not found")

    @_rule_handler
    def _handle_file_glob_check(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Detect unwanted files by glob patterns."""
        condition = rule.get("condition", {}) or {}
        patterns = condition.get("patterns", [])
        if not patterns or not isinstance(patterns, list):
            return _create_result("fail", "Missing 'patterns' list for file_glob_check")
        matches: List[str] = []
        try:
            for pat in patterns:
                for p in iter_project_files(path, pat):
                    matches.append(str(p.relative_to(path)))
                    if len(matches) >= 5:
                        break
                if len(matches) >= 5:
                    break
        except Exception as exc:
            return _handle_specific_exceptions("checking file globs", exc)
        if matches:
            return _create_result("fail", f"Found unwanted files: {matches[:5]}")
        return _create_result("pass", "No unwanted files detected")

    @_rule_handler
    def _handle_source_code_contains(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Handle source code keyword search checks (string or AST mode)."""
        condition = rule.get("condition", {}) or {}
        params = parse_source_code(condition)
        if params is None:
            return _create_result("fail", "Missing or invalid 'keyword' in condition")
        keyword, mode = params

        found = False
        if mode == "ast":
            # Support pipe-separated identifiers like "@app.|@bp." so that both
            # standard (@app.route) and Blueprint-style (@bp.route) are recognised.
            raw_parts = keyword.strip().split("|")
            ast_identifier = "|".join(p.strip().lstrip("@").rstrip(".") for p in raw_parts)
            if not ast_identifier:
                return _create_result("fail", "Invalid 'keyword' for AST mode")
            for _py_file, content in _iter_project_py_contents(path):
                if _source_contains_ast(content, ast_identifier):
                    found = True
                    break
        else:
            for _py_file, content in _iter_project_py_contents(path):
                if keyword in content:
                    found = True
                    break

        detail_suffix = " (AST)" if mode == "ast" else ""
        return _create_result(
            "pass" if found else "fail",
            (
                f"Keyword '{keyword}' {'found' if found else 'not found'} "
                f"in source code{detail_suffix}"
            ),
        )
