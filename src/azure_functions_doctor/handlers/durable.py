"""Durable Functions handlers (domain module, issue #387).

Split out of handlers/registry.py; registration/dispatch stays there.
"""

from pathlib import Path
from typing import Optional

from azure_functions_doctor.handlers._helpers import (
    HandlerResult,
    Rule,
    RuleContext,
    _collect_orchestrator_nondeterminism,
    _create_result,
    _rule_handler,
)


class DurableHandlers:
    """Durable Functions handlers: orchestrator/entity determinism."""

    @_rule_handler
    def _handle_durable_nondeterminism(
        self, rule: Rule, path: Path, context: Optional[RuleContext] = None
    ) -> HandlerResult:
        """Fail when orchestrator functions call nondeterministic APIs."""
        condition = rule.get("condition", {}) or {}
        blocklist = set(
            condition.get("blocklist")
            or [
                "datetime.now",
                "datetime.utcnow",
                "datetime.today",
                "time.time",
                "time.monotonic",
                "time.perf_counter",
                "random.random",
                "random.randint",
                "random.uniform",
                "random.choice",
                "random.randrange",
                "random.getrandbits",
                "uuid.uuid4",
                "uuid.uuid1",
                "requests.get",
                "requests.post",
                "requests.put",
                "requests.delete",
                "requests.patch",
                "requests.head",
                "open",
                "os.getenv",
                "os.environ.get",
            ]
        )
        decorator_names = set(
            condition.get("decorator_names") or ["orchestration_trigger", "entity_trigger"]
        )
        flagged = _collect_orchestrator_nondeterminism(path, blocklist, decorator_names)
        if not flagged:
            return _create_result("pass", "No nondeterministic calls detected in orchestrators")
        detail = "\n".join(
            [
                "Nondeterministic calls detected in orchestrator/entity functions:",
                *[f"- {loc}" for loc in flagged[:10]],
                "",
                "Fix: move nondeterministic work into activity functions.",
            ]
        )
        first = flagged[0] if flagged else None
        return _create_result(
            "fail",
            detail,
            file=first[0].split(" ->")[0].rsplit(":", 1)[0] if first else None,
            line=first[1] if first else None,
            locations=[
                {
                    "file": lbl.split(" ->")[0].rsplit(":", 1)[0],
                    "line": ln,
                    "message": f"Nondeterministic orchestrator call: {lbl}",
                }
                for lbl, ln in flagged[:10]
            ],
        )
