"""Binding-connection handlers and evaluators (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

from pathlib import Path
from typing import Optional, Sequence

from azure_functions_doctor.deploy_config import (
    local_settings_values,
)
from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    RuleContext,
    _collect_binding_connections,
    _create_result,
    _rule_handler,
)


def _normalize_reference(
    ref: tuple[str, str] | tuple[str, str, int],
) -> tuple[str, str, int]:
    """Accept 2-tuples (legacy/tests) and 3-tuples (collector, with lineno)."""
    if len(ref) == 3:
        name, label, lineno = ref
        return name, label, lineno
    name, label = ref
    return name, label, 0


def _evaluate_binding_connection_resolution(
    references: Sequence[tuple[str, str] | tuple[str, str, int]],
    app_settings: dict[str, str],
) -> HandlerResult:
    """Resolve v2 binding ``connection`` references against configured settings (#352).

    A referenced connection name is satisfied when an app setting matches it exactly
    or when an identity-based setting group is present (any ``<name>__...`` key, e.g.
    ``MyConn__serviceUri`` / ``MyConn__accountName``). References that resolve to no
    configuration are reported as a non-gating WARN so a project cannot silently ship
    a trigger whose connection will fail to bind at runtime. When no binding
    references a named connection, the check PASSes.
    """
    if not references:
        return _create_result(
            "pass",
            "No named binding connections referenced in v2 decorators.",
        )
    setting_names = set(app_settings)
    identity_prefixes = {name.split("__", 1)[0] for name in setting_names if "__" in name}

    def _is_resolved(name: str) -> bool:
        return name in setting_names or name in identity_prefixes

    unresolved: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for raw_ref in references:
        name, label, lineno = _normalize_reference(raw_ref)
        if _is_resolved(name):
            continue
        key = (name, label)
        if key in seen:
            continue
        seen.add(key)
        unresolved.append((name, label, lineno))

    if not unresolved:
        return _create_result(
            "pass",
            "All referenced binding connections resolve to configured settings.",
        )

    lines = ["Binding connections reference unconfigured settings:"]
    lines.extend(f"  - {name} ({label})" for name, label, _ln in unresolved)
    lines.append(
        "Add the missing app setting(s), or configure an identity-based connection "
        "group (<name>__serviceUri / <name>__accountName)."
    )
    detail = "\n".join(lines)
    # One location per unresolved reference so each lands on its binding
    # decorator line in SARIF (issue #394).
    locations: list[dict[str, object]] = [
        {
            "file": label.rsplit(":", 1)[0],
            "line": lineno if lineno > 0 else None,
            "message": f"Binding connection '{name}' ({label}) has no matching app setting",
        }
        for name, label, lineno in unresolved[:10]
    ]
    first = unresolved[0]
    result = _create_result(
        "fail",
        detail,
        file=first[1].rsplit(":", 1)[0],
        line=first[2] if first[2] > 0 else None,
        locations=locations,
    )
    result["severity"] = "warning"
    result["gate"] = False
    result["expected"] = "Every referenced binding connection has a matching app setting"
    result["actual"] = "Unresolved connections: " + ", ".join(
        sorted({name for name, _label, _ln in unresolved})
    )
    return result


class BindingHandlers:
    """Binding-connection handlers and evaluators.

    Resolves ``connection=`` references against configured settings.
    """

    @_rule_handler
    def _handle_binding_connection_resolution(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Resolve v2 binding ``connection`` references against configuration (#352).

        Collects ``connection="..."`` references from v2 trigger/binding decorators
        and resolves each against ``local.settings.json`` Values plus the ingested
        deploy-config app settings. Unresolved connections WARN (non-gating);
        identity-based connection groups (``<name>__...``) suppress false positives.
        """
        references = _collect_binding_connections(path)
        settings: dict[str, str] = dict(local_settings_values(path))
        target_config = context.get("target_config") if context is not None else None
        if target_config is not None:
            settings.update(target_config.app_settings)
        return _evaluate_binding_connection_resolution(references, settings)
