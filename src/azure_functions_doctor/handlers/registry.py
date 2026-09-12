"""Type-based handler registration and dispatch (issue #387 split).

Domain implementations live in the sibling modules (generic, dependencies,
runtime, monitoring, deployment, bindings, project, durable, integrations);
HandlerRegistry composes them as mixins and owns only registration and
dispatch. Public names are re-exported here for backward compatibility.
"""

from pathlib import Path
from typing import Callable, Dict, Optional

from azure_functions_doctor.handlers._helpers import (
    _RULE_DISPATCH,
    HandlerResult,
    Rule,
    RuleContext,
    _create_result,
    _handle_specific_exceptions,
)
from azure_functions_doctor.handlers.bindings import BindingHandlers  # noqa: E402
from azure_functions_doctor.handlers.bindings import (  # noqa: E402,F401
    _evaluate_binding_connection_resolution as _evaluate_binding_connection_resolution,
)
from azure_functions_doctor.handlers.dependencies import DependencyHandlers  # noqa: E402
from azure_functions_doctor.handlers.deployment import (  # noqa: E402,F401
    FLEX_CONSUMPTION_PLAN as FLEX_CONSUMPTION_PLAN,
)
from azure_functions_doctor.handlers.deployment import (
    FLEX_DEPRECATED_APP_SETTINGS as FLEX_DEPRECATED_APP_SETTINGS,
)
from azure_functions_doctor.handlers.deployment import DeploymentHandlers  # noqa: E402
from azure_functions_doctor.handlers.deployment import (
    _evaluate_flex_deployment_storage as _evaluate_flex_deployment_storage,
)
from azure_functions_doctor.handlers.deployment import (
    _evaluate_flex_deprecated_settings as _evaluate_flex_deprecated_settings,
)
from azure_functions_doctor.handlers.deployment import (
    _evaluate_flex_extension_version as _evaluate_flex_extension_version,
)
from azure_functions_doctor.handlers.deployment import (
    _evaluate_flex_runtime_config as _evaluate_flex_runtime_config,
)
from azure_functions_doctor.handlers.deployment import (
    _infra_declares_linux_fx_version as _infra_declares_linux_fx_version,
)
from azure_functions_doctor.handlers.durable import DurableHandlers  # noqa: E402

# Domain evaluator re-exports (backward compatibility) --------------------
from azure_functions_doctor.handlers.generic import GenericHandlers  # noqa: E402
from azure_functions_doctor.handlers.integrations import IntegrationHandlers  # noqa: E402
from azure_functions_doctor.handlers.monitoring import MonitoringHandlers  # noqa: E402
from azure_functions_doctor.handlers.project import ProjectHandlers  # noqa: E402
from azure_functions_doctor.handlers.runtime import (  # noqa: E402,F401
    FUNCTIONS_RUNTIME_CURRENT as FUNCTIONS_RUNTIME_CURRENT,
)
from azure_functions_doctor.handlers.runtime import (
    HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS as HOSTING_PLAN_RETIRING_SOON_WINDOW_DAYS,
)
from azure_functions_doctor.handlers.runtime import (
    PYTHON_RETIRING_SOON_WINDOW_DAYS as PYTHON_RETIRING_SOON_WINDOW_DAYS,
)
from azure_functions_doctor.handlers.runtime import RuntimeHandlers  # noqa: E402
from azure_functions_doctor.handlers.runtime import (
    _attach_catalog_evidence as _attach_catalog_evidence,
)
from azure_functions_doctor.handlers.runtime import (
    _evaluate_functions_runtime_lifecycle as _evaluate_functions_runtime_lifecycle,
)
from azure_functions_doctor.handlers.runtime import (
    _evaluate_hosting_plan_lifecycle as _evaluate_hosting_plan_lifecycle,
)
from azure_functions_doctor.handlers.runtime import (
    _evaluate_python_lifecycle as _evaluate_python_lifecycle,
)
from azure_functions_doctor.handlers.runtime import (
    _normalize_functions_runtime as _normalize_functions_runtime,
)


class HandlerRegistry(
    GenericHandlers,
    DependencyHandlers,
    RuntimeHandlers,
    MonitoringHandlers,
    DeploymentHandlers,
    BindingHandlers,
    ProjectHandlers,
    DurableHandlers,
    IntegrationHandlers,
):
    """Registry for diagnostic check handlers with individual handler methods."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[[Rule, Path, Optional[RuleContext]], HandlerResult]] = {
            check_type: getattr(self, method_name)
            for check_type, method_name in _RULE_DISPATCH.items()
        }

    def handle(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Route rule execution to appropriate handler."""
        check_type = rule.get("type")
        if check_type is None:
            return _create_result("fail", "Missing check type in rule")
        handler = self._handlers.get(check_type)

        if not handler:
            return _create_result("fail", f"Unknown check type: {check_type}")

        try:
            return handler(rule, path, context)
        except Exception as exc:
            return _handle_specific_exceptions(f"executing {check_type} check", exc)


# Global registry instance
_registry = HandlerRegistry()


def generic_handler(rule: Rule, path: Path, context: Optional[RuleContext] = None) -> HandlerResult:
    """
    Execute a diagnostic rule based on its type and condition.

    This function maintains backward compatibility while delegating to the registry.

    Args:
        rule: The diagnostic rule to execute.
        path: Path to the Azure Functions project.

    Returns:
        A dictionary with the status and detail of the check.
    """
    return _registry.handle(rule, path, context)
