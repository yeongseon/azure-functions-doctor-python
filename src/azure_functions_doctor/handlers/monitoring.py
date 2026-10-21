"""Telemetry/observability handlers (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

import json
import os
from pathlib import Path

from azure_functions_doctor.deploy_config import local_settings_values
from azure_functions_doctor.handlers._helpers import (
    _HOST_JSON_MISSING,
    HandlerResult,
    Rule,
    RuleContext,
    _create_result,
    _handle_specific_exceptions,
    _resolve_host_json_pointer,
    _rule_handler,
    logger,
)


class MonitoringHandlers:
    """Telemetry/observability handlers.

    Application Insights connection strings, host.json log-level conflicts.
    """

    @_rule_handler
    def _handle_app_insights_connection(
        self, rule: Rule, path: Path, context: RuleContext | None = None
    ) -> HandlerResult:
        """Validate Application Insights connection configuration.

        Technical support for instrumentation-key-based global ingestion
        ended 2025-03-31 (Microsoft continues to accept data sent to that
        path without further updates or customer support for it), so a
        connection string (``APPLICATIONINSIGHTS_CONNECTION_STRING``) is now
        recommended. A legacy instrumentation key (``APPINSIGHTS_INSTRUMENTATIONKEY``
        or ``host.json:instrumentationKey``) is treated as stale, and
        ``APPLICATIONINSIGHTS_AUTHENTICATION_STRING`` is recognised for Entra
        (AAD) authentication.

        Values are resolved with precedence current process environment >
        ``local.settings.json`` > the resolved deployment target context
        (#584), so a setting already ingested from a supported ARM/Bicep
        ``siteConfig.appSettings`` declaration is used instead of being
        reported as unconfigured -- the existing local/environment-only
        fallback (#519) is unchanged when no deployment declaration exists.
        """
        local = local_settings_values(path)
        target_config = context.get("target_config") if context is not None else None
        resolved_settings = dict(target_config.app_settings) if target_config is not None else {}
        setting_sources: dict[str, str] = (
            dict(target_config.app_settings_files) if target_config is not None else {}
        )
        for name in local:
            setting_sources.setdefault(name, "local.settings.json")

        def _resolve_setting(name: str) -> tuple[str, str]:
            """Resolve one setting's value and its provenance file, so a
            finding never blames a nonexistent local.settings.json for a
            setting that actually came from a resolved IaC declaration."""
            env_value = os.getenv(name)
            if env_value:
                return env_value.strip(), "local.settings.json"
            local_value = local.get(name, "")
            if local_value:
                return local_value.strip(), "local.settings.json"
            iac_value = resolved_settings.get(name, "")
            if iac_value:
                return iac_value.strip(), setting_sources.get(name, "local.settings.json")
            return "", "local.settings.json"

        conn, conn_file = _resolve_setting("APPLICATIONINSIGHTS_CONNECTION_STRING")
        auth, _ = _resolve_setting("APPLICATIONINSIGHTS_AUTHENTICATION_STRING")
        ik_env, ik_env_file = _resolve_setting("APPINSIGHTS_INSTRUMENTATIONKEY")

        ik_host = False
        host_path = path / "host.json"
        if host_path.exists():
            try:
                data = json.loads(host_path.read_text(encoding="utf-8-sig"))
                node = _resolve_host_json_pointer(data, ["instrumentationKey"])
                ik_host = node is not _HOST_JSON_MISSING and node is not None
            except json.JSONDecodeError as exc:
                logger.debug(f"Skip invalid host.json while checking App Insights: {exc}")

        has_ik = bool(ik_env) or ik_host
        ik_file = "host.json" if (ik_host and not ik_env) else ik_env_file
        auth_note = (
            " Entra auth via APPLICATIONINSIGHTS_AUTHENTICATION_STRING is configured."
            if auth
            else ""
        )

        if conn:
            if has_ik:
                return _create_result(
                    "fail",
                    "Connection string is set, but a legacy instrumentation key is "
                    "also configured; remove it (support for instrumentation-key-based "
                    "global ingestion ended 2025-03-31)." + auth_note,
                    file=ik_file,
                )
            return _create_result(
                "pass",
                "Application Insights connection string configured." + auth_note,
            )

        if has_ik:
            return _create_result(
                "fail",
                "Only a legacy Application Insights instrumentation key is configured; "
                "support for instrumentation-key-based global ingestion ended "
                "2025-03-31. Set APPLICATIONINSIGHTS_CONNECTION_STRING instead." + auth_note,
                file=ik_file,
            )

        if auth:
            return _create_result(
                "fail",
                "Application Insights Entra authentication "
                "(APPLICATIONINSIGHTS_AUTHENTICATION_STRING) is configured, but "
                "APPLICATIONINSIGHTS_CONNECTION_STRING is missing; set the connection "
                "string to enable telemetry.",
                file=conn_file,
            )

        return _create_result(
            "fail",
            "Application Insights is not configured; set "
            "APPLICATIONINSIGHTS_CONNECTION_STRING to enable telemetry.",
            file="local.settings.json",
        )

    @_rule_handler
    def _handle_host_json_log_level_conflict(
        self, rule: Rule, path: Path, context: RuleContext | None = None
    ) -> HandlerResult:
        """Flag host.json logLevel entries that conflict with the default level.

        ``logging.logLevel`` category overrides win over ``default``. When a
        category is configured *more verbose* than ``default`` it silently
        overrides the intended-restrictive default, producing more logs (and
        cost/PII exposure) than expected — a common misconfiguration.
        """
        host_path = path / "host.json"
        if not host_path.exists():
            return _create_result("skip", "host.json not found; logLevel check skipped")
        try:
            host_data = json.loads(host_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            return _handle_specific_exceptions("reading host.json", exc)
        logging_cfg = host_data.get("logging") if isinstance(host_data, dict) else None
        log_level = logging_cfg.get("logLevel") if isinstance(logging_cfg, dict) else None
        if not isinstance(log_level, dict) or "default" not in log_level:
            return _create_result(
                "skip", "host.json has no logging.logLevel.default; conflict check skipped"
            )
        rank = {
            "trace": 0,
            "debug": 1,
            "information": 2,
            "warning": 3,
            "error": 4,
            "critical": 5,
            "none": 6,
        }
        default_rank = rank.get(str(log_level["default"]).strip().lower())
        if default_rank is None:
            return _create_result(
                "fail",
                f"host.json logging.logLevel.default '{log_level['default']}' "
                "is not a recognized log level.",
                file="host.json",
            )
        conflicts: list[str] = []
        for category, level in log_level.items():
            if category == "default":
                continue
            category_rank = rank.get(str(level).strip().lower())
            if category_rank is not None and category_rank < default_rank:
                conflicts.append(
                    f"- {category}={level} is more verbose than default={log_level['default']}"
                )
        if not conflicts:
            return _create_result(
                "pass", "host.json logLevel categories are consistent with default"
            )
        detail = "\n".join(
            [
                "host.json logLevel category overrides conflict with the default level:",
                *conflicts[:10],
                "",
                "Fix: lower the category level(s) to match the intended default, or "
                "raise the default deliberately.",
            ]
        )
        return _create_result("fail", detail)
