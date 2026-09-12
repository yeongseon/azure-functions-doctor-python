# Handlers

Handlers execute rule definitions from `src/azure_functions_doctor/assets/rules/v2.json`.

Each rule has a `type`, and `HandlerRegistry` routes the rule to the corresponding
handler implementation in the `src/azure_functions_doctor/handlers/` package.
`registry.py` owns registration and dispatch only; implementations live in
per-domain modules composed as mixins (issue #387):

| Module | Domain |
| --- | --- |
| `generic.py` | Version comparison, path/file/env/executable detection |
| `dependencies.py` | requirements.txt / pyproject declarations, native-deployment risk, pinning |
| `runtime.py` | Python / Functions runtime / hosting-plan lifecycle evaluators |
| `monitoring.py` | Application Insights connection strings, host.json log-level conflicts |
| `deployment.py` | Flex Consumption, FUNCTIONS_EXTENSION_VERSION, linuxFxVersion, host.json/site config |
| `bindings.py` | Binding `connection=` resolution |
| `project.py` | Blueprint registration, decorator ordering |
| `durable.py` | Durable orchestrator determinism |
| `integrations.py` | Endpoint metadata, OpenAPI versioning, LangGraph, OTel |

Shared primitives stay in `_helpers.py`, and every public name is re-exported
from `registry.py` for backward compatibility. The public import path
`azure_functions_doctor.handlers` is preserved.

## Contract

- Input: `rule` and project `path`
- Output: a dictionary with `status` and `detail`
- Status values: `pass` or `fail`

Optional rules are converted to `warn` later in the aggregation layer.

### Rule Input Contract

Rules are JSON objects validated by the schema in
`src/azure_functions_doctor/schemas/rules.schema.json`.
The minimum practical structure for handler execution is:

```json
{
  "id": "check_example",
  "type": "file_exists",
  "label": "host.json",
  "required": true,
  "condition": {
    "target": "host.json"
  }
}
```

### Handler Output Contract

Handlers return a normalized dictionary:

| Key | Type | Meaning |
| --- | --- | --- |
| `status` | `"pass"` or `"fail"` | Raw check result before optional-to-warn mapping. |
| `detail` | `str` | Human-readable diagnostic detail used in reports. |
| `internal_error` | `"true"` (optional) | Present when an internal exception is captured. |

## HandlerRegistry Pattern

`HandlerRegistry` centralizes dispatch so each rule type maps to one method.
This keeps `Doctor` focused on orchestration while handlers focus on evaluation.

Dispatch flow:

1. `Doctor.run_all_checks()` passes each rule to `generic_handler(rule, path)`.
2. `generic_handler` forwards execution to a global `HandlerRegistry` instance.
3. `HandlerRegistry.handle()` resolves `rule["type"]`.
4. A concrete `_handle_*` method returns `{"status": ..., "detail": ...}`.
5. `Doctor` maps optional failures to `warn` and builds section results.

## Built-in Handlers

- `compare_version`
- `env_var_exists`
- `path_exists`
- `file_exists`
- `dependency_manifest`
- `package_installed`
- `package_declared`
- `package_forbidden`
- `native_dependency_risk`
- `source_code_contains`
- `conditional_exists`
- `callable_detection`
- `executable_exists`
- `any_of_exists`
- `file_glob_check`
- `host_json_property`
- `host_json_version`
- `host_json_extension_bundle_version`
- `local_settings_security`
- `blueprint_registration`
- `decorator_order`
- `endpoint_metadata`
- `openapi_version_mixing`
- `scan_before_spec`
- `langgraph_anonymous_auth`
- `durable_nondeterminism`
- `unsupported_metadata_version`

The authoritative dispatch map is `_RULE_DISPATCH` in
`src/azure_functions_doctor/handlers/_helpers.py`.

### Handler Reference

| Handler Type | Condition Keys | Typical Use |
| --- | --- | --- |
| `compare_version` | `target`, `operator`, `value` | Python version and Core Tools version checks. |
| `env_var_exists` | `target` | Environment variable presence checks. |
| `path_exists` | `target` | Check concrete paths or `sys.executable`. |
| `file_exists` | `target` | Required project files (`host.json`, `requirements.txt`). |
| `dependency_manifest` | optional `target` | Pass when dependencies are declared via `requirements.txt` **or** `pyproject.toml`. |
| `package_installed` | `target` | Validate importable module availability. |
| `package_declared` | `package`, optional `file` | Confirm package declaration in dependency file (falls back to `pyproject.toml`). |
| `package_forbidden` | `package`, optional `file` | Warn when a platform-managed package (e.g. `azure-functions-worker`) is pinned. |
| `native_dependency_risk` | optional `file` | Warn when packages with native-extension deployment risk are declared. |
| `source_code_contains` | `keyword`, optional `mode` | Detect decorators or source signals (string or `ast` mode). |
| `conditional_exists` | `jsonpath` | Conditional host checks (for example Durable settings). |
| `callable_detection` | none | Detect ASGI/WSGI callable exposure patterns. |
| `executable_exists` | `target` | Ensure local binaries exist on `PATH`. |
| `any_of_exists` | `targets` | Pass when any env/file/host signal is present. |
| `app_insights_connection` | none | Require an Application Insights connection string; flag legacy instrumentation keys. |
| `file_glob_check` | `patterns` | Detect junk files and deployment artifacts. |
| `host_json_property` | `jsonpath` | Validate specific host.json properties. |
| `host_json_version` | none | Validate `host.json` declares `"version": "2.0"`. |
| `host_json_extension_bundle_version` | none | Validate `extensionBundle` uses the recommended v4 range. |
| `local_settings_security` | none | Warn when `local.settings.json` is tracked by git. |
| `blueprint_registration` | none | Warn when decorated Blueprint aliases are never registered. |
| `decorator_order` | optional `decorators` | Warn when `@validate_http` is stacked outside `@with_context`. |
| `endpoint_metadata` | none | Warn when route handlers lack `@validate_http` in a validation-enabled project. |
| `openapi_version_mixing` | none | Warn when OpenAPI 3.0 and 3.1 signals both appear. |
| `scan_before_spec` | optional `scan_names`, `spec_names` | Warn when the OpenAPI spec is built before endpoints are scanned. |
| `langgraph_anonymous_auth` | optional `flag_missing_auth_level` | Warn when a LangGraph project exposes anonymous-auth routes. |
| `durable_nondeterminism` | optional `blocklist`, `decorator_names` | Fail when orchestrator/entity functions call nondeterministic APIs. |
| `unsupported_metadata_version` | optional `files`, `fields`, `supported_versions` | Warn when metadata declares an unsupported version. |

## Example Rule JSON by Handler Type

```json
[
  {
    "id": "python_min",
    "type": "compare_version",
    "condition": {"target": "python", "operator": ">=", "value": "3.10"}
  },
  {
    "id": "venv_active",
    "type": "env_var_exists",
    "condition": {"target": "VIRTUAL_ENV"}
  },
  {
    "id": "python_path",
    "type": "path_exists",
    "condition": {"target": "sys.executable"}
  },
  {
    "id": "host_file",
    "type": "file_exists",
    "condition": {"target": "host.json"}
  },
  {
    "id": "module_installed",
    "type": "package_installed",
    "condition": {"target": "azure.functions"}
  },
  {
    "id": "package_declared",
    "type": "package_declared",
    "condition": {"package": "azure-functions", "file": "requirements.txt"}
  },
  {
    "id": "decorator_signal",
    "type": "source_code_contains",
    "condition": {"keyword": "@app.", "mode": "ast"}
  },
  {
    "id": "durable_host",
    "type": "conditional_exists",
    "condition": {"jsonpath": "$.extensions.durableTask"}
  },
  {
    "id": "asgi_wsgi",
    "type": "callable_detection",
    "condition": {}
  },
  {
    "id": "func_cli",
    "type": "executable_exists",
    "condition": {"target": "func"}
  },
  {
    "id": "telemetry_any",
    "type": "any_of_exists",
    "condition": {
      "targets": [
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "APPINSIGHTS_INSTRUMENTATIONKEY",
        "host.json:instrumentationKey"
      ]
    }
  },
  {
    "id": "junk_files",
    "type": "file_glob_check",
    "condition": {"patterns": ["**/*.pyc", "**/__pycache__"]}
  },
  {
    "id": "extension_bundle",
    "type": "host_json_property",
    "condition": {"jsonpath": "$.extensionBundle"}
  }
]
```

## Notes

- `source_code_contains` supports a simple string mode and an AST-based mode.
- `conditional_exists` is used for checks that only matter when a related feature is detected.
- Handler implementations live in the `src/azure_functions_doctor/handlers/` package
  (domain modules listed above; dispatch in `registry.py`).

## Programmatic Usage Examples

### Execute One Rule Through `HandlerRegistry`

```python
from pathlib import Path

from azure_functions_doctor.handlers import HandlerRegistry


def run_host_check(project_path: str) -> dict[str, str]:
    registry = HandlerRegistry()
    rule = {
        "id": "host_file",
        "type": "file_exists",
        "label": "host.json",
        "required": True,
        "condition": {"target": "host.json"},
    }
    return registry.handle(rule=rule, path=Path(project_path))
```

### Register a Custom Handler in a Subclass

```python
from pathlib import Path

from azure_functions_doctor.handlers import HandlerRegistry


class ExtendedRegistry(HandlerRegistry):
    def __init__(self) -> None:
        super().__init__()
        self._handlers["always_pass"] = self._handle_always_pass

    def _handle_always_pass(self, rule: dict, path: Path, context=None) -> dict[str, str]:
        _ = (rule, path, context)
        return {"status": "pass", "detail": "Custom handler executed"}


def run_custom_rule(project_path: str) -> dict[str, str]:
    registry = ExtendedRegistry()
    custom_rule = {
        "id": "custom_demo",
        "type": "always_pass",
        "condition": {},
    }
    return registry.handle(custom_rule, Path(project_path))
```

## Development

When adding a new handler:

1. Extend the `Rule["type"]` literal in `handlers/_helpers.py`
2. Implement `_handle_<name>(self, rule, path, context=None)` in the matching domain
   module under `handlers/` (or a new one, added to the `HandlerRegistry` mixin bases in
   `registry.py`), decorated with `@_rule_handler` (which registers it in
   `_RULE_DISPATCH`; `HandlerRegistry.__init__` binds it automatically)
3. Update `rules.schema.json`
4. Add tests in `tests/test_handler.py`
