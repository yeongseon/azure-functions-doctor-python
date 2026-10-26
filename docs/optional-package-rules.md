# Optional companion-package heuristics

These built-in rules are advisory: they do not change the required checks in
`--profile minimal` or make companion packages mandatory. Source discovery is
static; Doctor never imports application modules to discover these features.

| Rule | Evidence required before advice applies | Value | Confidence and false-positive boundary |
| --- | --- | --- | --- |
| `check_decorator_order` | Validation distribution in requirements (including supported includes), or an `azure_functions_validation` import | Finds validation outside SDK binding decorators or inverted logging/validation stacking | Decorator leaf names are heuristic after the package gate; unrelated decorators with the same names inside a validation project can still match. Aliases/Blueprint binding receivers use existing discovery. |
| `check_endpoint_metadata` | `azure-functions-validation` declared in requirements | Identifies HTTP routes missing validation metadata; excludes recognized spec-serving handlers | Not every HTTP endpoint needs validation. Treat the finding as coverage advice, not proof that a handler is broken. |
| `check_openapi_version_mixing` | `azure-functions-openapi` declared in requirements | Surfaces mixed 3.0/3.1/3.2 signals | String versions and `nullable` are heuristics, not a schema validator; unrelated version constants in an OpenAPI project may match. |
| `check_scan_before_spec` | `azure-functions-openapi` declared in requirements | Finds apparent spec building before endpoint scanning/registration | Leaf call names and textual order cannot prove runtime execution order; indirect factories may be missed. |
| `check_langgraph_anonymous_auth` | A `langgraph` or `langgraph.*` import | Reviews anonymous routes in graph-enabled projects | Anonymous access can be intentional or protected upstream. Import evidence is not a full reachability analysis. |
| `check_otel_trace_context_activation` | Logging distribution in requirements or `azure_functions_logging` import, plus an explicit activation call | Detects requested activation without a declared OTel package or logging `[otel]` extra | Activation call names remain heuristic; dynamically installed dependencies cannot be proven from the manifest. No logging evidence means skip, not a warning. |

Absent package evidence causes the relevant built-in rule to skip. The
decorator-order and OTel handler types remain usable by custom rules with their
own conditions; the shipped rule IDs receive the package gates. Manifest-based
checks intentionally do not execute installed packages or attempt whole-program
inference. Other optional checks such as Blueprint registration and Durable
orchestrator determinism concern the Functions programming model itself, not a
requirement to install a toolkit companion.

The two OpenAPI rules share a manifest precondition but report different risks
(schema-version signals versus registration order), so they remain separate.
Endpoint metadata and decorator order similarly distinguish absent metadata
from unsafe wrapping order. None is promoted to a mandatory gate. Review
low-confidence findings against the application design; see the
[rule policy](RULE_POLICY.md) and [inventory](rule_inventory.md).
