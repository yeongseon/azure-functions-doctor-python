"""Programming-model handlers (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

from pathlib import Path
from typing import Optional

from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    RuleContext,
    _collect_inverted_decorator_order,
    _collect_unregistered_blueprint_aliases,
    _create_result,
    _rule_handler,
)


class ProjectHandlers:
    """Programming-model handlers: Blueprint registration, decorator ordering."""

    @_rule_handler
    def _handle_blueprint_registration(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when decorated Blueprint aliases are never registered."""
        unregistered_aliases = sorted(_collect_unregistered_blueprint_aliases(path))
        if not unregistered_aliases:
            return _create_result("pass", "All detected Blueprint aliases are registered")

        detail = "\n".join(
            [
                "Detected:",
                *[f"- {alias} = func.Blueprint()" for alias in unregistered_aliases],
                *[f"- @{alias}.route(...)" for alias in unregistered_aliases],
                "",
                "Missing:",
                *[f"- app.register_functions({alias})" for alias in unregistered_aliases],
                "",
                "Fix: add the missing `app.register_functions(<alias>)` call(s)"
                " in function_app.py.",
            ]
        )
        return _create_result("fail", detail)

    @_rule_handler
    def _handle_decorator_order(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Warn when decorators are stacked outside their expected inner order."""
        condition = rule.get("condition", {})
        # ``decorators`` lists the expected order outermost-first. Only the first
        # and last entries are surfaced in the fix message below, which is exact
        # for the shipped two-element pairing.
        expected_order = condition.get("decorators") or ["with_context", "validate_http"]
        inverted = _collect_inverted_decorator_order(path, expected_order)

        if not inverted:
            return _create_result("pass", "No inverted decorator order detected")
        detail = "\n".join(
            [
                "Inverted decorator order detected:",
                *[
                    f"- {fn}: @{expected_order[-1]} is outside @{expected_order[0]}"
                    for fn, _ln in inverted[:10]
                ],
                "",
                "Fix: reorder to @app.route -> "
                + " -> ".join(f"@{name}" for name in expected_order)
                + f" ({expected_order[-1]} innermost).",
            ]
        )
        first = inverted[0] if inverted else None
        return _create_result(
            "fail",
            detail,
            file=first[0].rsplit(":", 1)[0] if first else None,
            line=first[1] if first else None,
            locations=[
                {
                    "file": lbl.rsplit(":", 1)[0],
                    "line": ln,
                    "message": f"Inverted decorator order on {lbl}",
                }
                for lbl, ln in inverted[:10]
            ],
        )
