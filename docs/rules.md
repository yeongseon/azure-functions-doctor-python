# Rules

Azure Functions Doctor executes declarative rules from a JSON ruleset.

Built-in rules are defined in:

`src/azure_functions_doctor/assets/rules/v2.json`

You can replace the built-in set with `--rules <file>`.

## Rule execution model

Each rule contains:

- identity (`id`, `label`)
- grouping (`category`, `section`)
- behavior (`type`, `condition`)
- severity intent (`required`)
- ordering (`check_order`)
- remediation (`hint`, optional `hint_url`)

Rules are validated by:

`src/azure_functions_doctor/schemas/rules.schema.json`

## Required vs optional

- `required: true` + raw handler fail -> item status `fail`
- `required: false` + raw handler fail -> item status `warn`

Only required failures produce non-zero process exit code.

## Built-in rule types

The built-in ruleset uses the following handler types:

- `compare_version`
- `path_exists`
- `file_exists`
- `dependency_manifest`
- `package_declared`
- `package_forbidden`
- `native_dependency_risk`
- `source_code_contains`
- `blueprint_registration`
- `conditional_exists`
- `callable_detection`
- `executable_exists`
- `any_of_exists`
- `file_glob_check`
- `host_json_property`
- `host_json_version`
- `host_json_extension_bundle_version`
- `local_settings_security`
- `decorator_order`
- `endpoint_metadata`
- `openapi_version_mixing`
- `scan_before_spec`
- `langgraph_anonymous_auth`
- `durable_nondeterminism`
- `unsupported_metadata_version`
- `otel_activation`

For the authoritative, script-generated list of every built-in rule and its
type, see the [Rule Inventory](rule_inventory.md).

## Rule-by-rule reference

## 1) `check_programming_model_v2`

- **What it checks:** Source contains Azure Functions decorator usage (`@app.`) via AST detection.
- **Why it matters:** Doctor targets Python v2 projects; this check protects model compatibility.
- **How to fix:** Use `func.FunctionApp()` and decorator-based triggers.

Example failing detail:

```text
Keyword '@app.' not found in source code (AST)
```

## 2) `check_blueprint_registration`

- **What it checks:** Blueprint aliases declared with `func.Blueprint()` and used in decorators are also registered via `app.register_functions(bp)` somewhere in the project. Only the official Azure Functions Python v2 API is recognized; Flask/FastAPI-style `register_blueprint(...)` calls are not treated as registration.
- **Why it matters:** Unregistered Blueprints look valid in code but their routes never index at runtime.
- **How to fix:** Register each Blueprint on your `FunctionApp`, typically from `function_app.py`.

Example warning detail:

```text
Detected:
- bp = func.Blueprint()
- @bp.route(...)

Missing:
- app.register_functions(bp)

Fix: add `app.register_functions(bp)` in function_app.py.
```

## 3) `check_python_version`

- **What it checks:** Python version evaluated for the app target is `>=3.10`.
- **Why it matters:** Azure Functions Python runtime compatibility depends on the deployed target version, not just the interpreter running the doctor.
- **How to fix:** Use Python 3.10+ locally and in CI, or pass `--target-python <3.10|3.11|3.12|3.13|3.14>` when your deploy target differs from the tool runtime. Note that on the Linux Consumption plan the maximum supported runtime is Python 3.12.

Example output:

```text
Python 3.9.18 (tool runtime, >=3.10)
```

With override:

```text
Target Python: 3.12 (override) — Tool runtime: 3.13.0
```

## 4) `check_venv`

- **What it checks:** A virtual environment is activated — any of `VIRTUAL_ENV`, `CONDA_PREFIX`, or `UV_PROJECT_ENVIRONMENT` is set (venv, conda, or uv).
- **Why it matters:** Virtual environments reduce dependency drift and environment pollution.
- **How to fix:** Create and activate a virtual environment (`.venv`, conda, or uv) before running diagnostics.

Example failing detail:

```text
Targets not found
```

## 5) `check_python_executable`

- **What it checks:** `sys.executable` points to an existing path.
- **Why it matters:** Broken interpreter paths indicate unstable runtime environment.
- **How to fix:** Reinstall or reactivate Python environment.

Example detail:

```text
/usr/bin/python3 exists
```

## 6) `check_requirements_txt`

- **What it checks:** Dependencies are declared via `requirements.txt` or `pyproject.toml` at the project root.
- **Why it matters:** Deployability and reproducibility depend on declared dependencies.
- **How to fix:** Add `requirements.txt` (or declare dependencies in `pyproject.toml`) and include runtime dependencies.

Example failing detail:

```text
<path>/requirements.txt not found and pyproject.toml declares no dependencies
```

## 7) `check_azure_functions_library`

- **What it checks:** `azure-functions` is declared in `requirements.txt` or `pyproject.toml`.
- **Why it matters:** Function app code depends on Azure Functions Python library.
- **How to fix:** Add `azure-functions` to dependency declarations.

Example failing detail:

```text
Package 'azure-functions' not declared in requirements.txt
```

## 8) `check_native_dependency_risk`

- **What it checks:** `requirements.txt` for packages with common native-extension deployment risk.
- **Why it matters:** These packages are valid, but Azure Functions Python deployments often fail when Linux wheels or system libraries do not match the build environment.
- **How to fix:** Build against the Azure Functions Linux runtime. Prefer remote build with `func azure functionapp publish --build remote`.
- **Current package list:** `pyodbc`, `cryptography`, `lxml`, `pillow`, `numpy`, `pandas`, `scipy`, `opencv-python`, `psycopg2`, `grpcio`, `ujson`, `orjson`.
- **Severity:** Warning only (`required: false`). It never produces a hard failure.

Example warning detail:

```text
Native dependencies detected: pyodbc, pillow
These packages depend on platform-specific native libraries.
Ensure your build environment matches the Azure Functions Linux runtime.
Recommended: use remote build (`func azure functionapp publish --build remote`).
- pyodbc: requires unixODBC and a matching wheel
- pillow: ensure libjpeg/zlib-compatible wheels for Linux deployment
```

## 9) `check_host_json`

- **What it checks:** `host.json` exists at project root.
- **Why it matters:** Azure Functions host configuration is required for valid app structure.
- **How to fix:** Add a valid `host.json` (at minimum `{ "version": "2.0" }`).

Example failing detail:

```text
/workspace/app/host.json not found
```

## 10) `check_local_settings`

- **What it checks:** `local.settings.json` exists.
- **Why it matters:** Local development often needs this file for settings and connection values.
- **How to fix:** Create local settings file for local runs (do not commit secrets).

Example warning detail:

```text
/workspace/app/local.settings.json not found (optional)
```

## 11) `check_func_cli`

- **What it checks:** `func` executable is available on `PATH`.
- **Why it matters:** Core Tools enable local hosting and rich runtime tooling.
- **How to fix:** Install Azure Functions Core Tools v4+.

Example warning detail:

```text
func not found
```

## 12) `check_func_core_tools_version`

- **What it checks:** Core Tools version is `>=4.0`.
- **Why it matters:** Older versions can diverge from current host/runtime expectations.
- **How to fix:** Upgrade Core Tools installation.

Example warning detail:

```text
func 3.0.3904 (>=4.0)
```

## 13) `check_durabletask_config`

- **What it checks:** If durable usage is detected in source, `$.extensions.durableTask` exists in `host.json`.
- **Why it matters:** Durable Functions need matching host configuration.
- **How to fix:** Add durableTask configuration when using durable features.

Example details:

```text
No Durable Functions usage detected; check skipped
```

or

```text
Required host.json property '$.extensions.durableTask' not found
```

## 14) `check_app_insights`

- **What it checks:** Application Insights uses a **connection string**
  (`APPLICATIONINSIGHTS_CONNECTION_STRING`). A legacy instrumentation key
  (`APPINSIGHTS_INSTRUMENTATIONKEY` or `host.json:instrumentationKey`) is
  treated as stale, and `APPLICATIONINSIGHTS_AUTHENTICATION_STRING` is
  recognised for Entra (AAD) authentication.
- **Why it matters:** Instrumentation-key ingestion ended 2025-03-31, so a
  connection string is required for telemetry to reach Application Insights.
- **How to fix:** Set `APPLICATIONINSIGHTS_CONNECTION_STRING` and remove any
  legacy instrumentation key.

Example warning detail:

```text
Application Insights is not configured; set APPLICATIONINSIGHTS_CONNECTION_STRING to enable telemetry. (optional)
```

## 15) `check_extension_bundle`

- **What it checks:** `$.extensionBundle` exists in `host.json`.
- **Why it matters:** Extension bundles help ensure binding dependencies are available.
- **How to fix:** Add extensionBundle section to host config.

Example warning detail:

```text
host.json property '$.extensionBundle' not found
```

## 16) `check_asgi_wsgi_exposure`

- **What it checks:** Whether an ASGI/WSGI framework (FastAPI/Flask/Starlette/Quart)
  is wired into Azure Functions via `AsgiFunctionApp`/`WsgiFunctionApp` (or
  `AsgiMiddleware`/`WsgiMiddleware`).
- **Why it matters:** A plain decorator-based `FunctionApp` has no ASGI/WSGI app,
  so the check **skips** to avoid noise. A detected framework that is not exposed
  is a real wiring gap.
- **How to fix:** Expose the framework callable with `AsgiFunctionApp`/`WsgiFunctionApp`.

Example warning detail:

```text
ASGI/WSGI framework detected but no callable is exposed via AsgiFunctionApp/WsgiFunctionApp (or AsgiMiddleware/WsgiMiddleware); wire it into Azure Functions: ['main.py:\bFastAPI\s*\('] (optional)
```

## 17) `check_unused_files`

- **What it checks:** Presence of unwanted patterns (for example `**/*.pyc`, `**/__pycache__`, `.venv`, `tests/`).
- **Why it matters:** Reduces deployment package clutter and risk.
- **How to fix:** Clean or exclude unwanted files from deployment artifacts.

Example warning detail:

```text
Found unwanted files: ['tests/', '.venv']
```

## 18) `check_azure_functions_worker`

- **What it checks:** `azure-functions-worker` is **not** declared in `requirements.txt`.
- **Why it matters:** The Azure Functions platform manages the worker runtime; pinning it can cause deployment failures.
- **How to fix:** Remove `azure-functions-worker` from your dependency declarations.
- **Severity:** Warning only (`required: false`).

## 19) `check_host_json_version`

- **What it checks:** `host.json` declares `"version": "2.0"` as required by the v2 runtime.
- **Why it matters:** An incorrect or missing host version breaks v2 app indexing.
- **How to fix:** Set `{ "version": "2.0" }` in `host.json`.
- **Severity:** Required (`required: true`).

## 20) `check_funcignore`

- **What it checks:** A `.funcignore` file is present to control what gets deployed.
- **Why it matters:** Without it, unnecessary files can bloat the deployment package.
- **How to fix:** Add a `.funcignore` file excluding local-only paths.
- **Severity:** Warning only (`required: false`).

## 21) `check_local_settings_git_tracked`

- **What it checks:** `local.settings.json` is **not** tracked by git.
- **Why it matters:** Tracking it can leak secrets into version control.
- **How to fix:** Add `local.settings.json` to `.gitignore` and untrack it.
- **Severity:** Warning only (`required: false`).

## 22) `check_extension_bundle_v4`

- **What it checks:** `extensionBundle` in `host.json` uses a documented v4 range. The range is parsed as an interval (not a string prefix): the lower bound must be an inclusive major 4 (`[4.0.0` or `[4.*`) and the upper bound must be an exclusive `5.0.0)`. Over-broad ranges such as `[4.0.0, 6.0.0)` are rejected. The bundle id must be `Microsoft.Azure.Functions.ExtensionBundle`.
- **Why it matters:** Aligns binding extensions with the current supported bundle.
- **How to fix:** Update the `extensionBundle.version` range to the v4 range.
- **Severity:** Warning only (`required: false`).

## 23) `check_decorator_order`

- **What it checks:** `@validate_http` is not stacked outside `@with_context`. The correct order (top to bottom) is `@app.route` → `@with_context` → `@validate_http`.
- **Why it matters:** Incorrect decorator order changes request handling behavior.
- **How to fix:** Reorder decorators so `@with_context` wraps `@validate_http`.
- **Severity:** Warning only (`required: false`).

## 24) `check_endpoint_metadata`

- **What it checks:** In projects depending on `azure-functions-validation`, HTTP route handlers emit endpoint OpenAPI metadata via `@validate_http` **or** another supported metadata decorator (`@openapi`, LangGraph metadata). Routes annotated with those decorators are not flagged even without `@validate_http`.
- **Why it matters:** Handlers without it will not appear in generated OpenAPI specs.
- **How to fix:** Apply `@validate_http` — or another supported endpoint-metadata decorator (`@openapi` or the LangGraph metadata decorators) — to route handlers that should emit metadata.
- **Severity:** Warning only (`required: false`).

## 25) `check_openapi_version_mixing`

- **What it checks:** A project does not mix two or more OpenAPI versions. It recognizes 3.0 signals (3.0.x version strings or the `nullable` keyword), 3.1 signals (3.1.x strings), and **3.2** signals (3.2.x strings). A single-version project — including 3.2-only — never warns.
- **Why it matters:** Mixing versions produces inconsistent generated specs.
- **How to fix:** Standardize on a single OpenAPI version across the project.
- **Severity:** Warning only (`required: false`).

## 26) `check_scan_before_spec`

- **What it checks:** The OpenAPI spec is not built before endpoints are scanned/registered (and not built without any endpoint scan).
- **Why it matters:** Building the spec too early yields an empty or incomplete spec.
- **How to fix:** Scan/register endpoints before building the spec.
- **Severity:** Warning only (`required: false`).

## 27) `check_langgraph_anonymous_auth`

- **What it checks:** In projects that import `langgraph`, HTTP routes do not use `auth_level` set to `ANONYMOUS`.
- **Why it matters:** Anonymous auth leaves graph endpoints publicly reachable.
- **How to fix:** Set a non-anonymous `auth_level` for LangGraph HTTP routes.
- **Severity:** Warning only (`required: false`).

## 28) `check_durable_nondeterminism`

- **What it checks:** Orchestration or entity trigger functions do not call nondeterministic APIs (`datetime.now`, `random`, `uuid`, `requests`, `open`, `os.getenv`).
- **Why it matters:** Nondeterministic calls break Durable Functions replay.
- **How to fix:** Move nondeterministic work into activity functions.
- **Severity:** Required (`required: true`).

## 29) `check_otel_trace_context_activation`

- **What it checks:** In projects that opt into `azure-functions-logging` trace-context activation (`activate_trace_context=True` or `set_default_trace_context_activation`), an `opentelemetry` distribution is declared in `requirements.txt` or `pyproject.toml`.
- **Why it matters:** `azure-functions-logging` silently degrades activation to a no-op when OpenTelemetry is unavailable, so requested trace context is dropped without any runtime error.
- **How to fix:** Install the `azure-functions-logging[otel]` extra (or an `opentelemetry-*` package), or disable `activate_trace_context`.
- **Severity:** Warning only (`required: false`).


## Deploy-risk rule reference

The runtime/hosting/deployment-correctness rules also have individual reference pages under `docs/rules/`. Each page shows the exact finding text, so searching for an error message lands directly on the rule:

- [Python runtime lifecycle](rules/check_python_runtime_lifecycle.md)
- [Functions runtime lifecycle](rules/check_functions_runtime_lifecycle.md)
- [Hosting plan lifecycle](rules/check_hosting_plan_lifecycle.md)
- [Flex Consumption runtime config](rules/check_flex_runtime_config.md)
- [Flex Consumption deprecated app settings](rules/check_flex_deprecated_settings.md)
- [Flex Consumption deployment storage](rules/check_flex_deployment_storage.md)
- [Binding connection resolution](rules/check_binding_connection_resolution.md)
- [Functions extension version](rules/check_functions_extension_version.md)
- [Linux runtime (linuxFxVersion)](rules/check_linux_fx_version.md)
- [Dev-storage emulator connection](rules/check_dev_storage_connection.md)
- [Pinned requirements](rules/check_unpinned_requirements.md)

Experimental-tier and integration-group rules are intentionally not given per-rule pages yet (see [#326](https://github.com/yeongseon/azure-functions-doctor-python/issues/326)).

## Rule authoring template

```json
{
  "id": "check_example",
  "category": "structure",
  "section": "project_structure",
  "label": "host.json",
  "description": "Checks host.json exists.",
  "type": "file_exists",
  "required": true,
  "condition": {
    "target": "host.json"
  },
  "hint": "Add host.json to project root.",
  "check_order": 10
}
```

## Guidance for custom rules

- Keep IDs stable and descriptive
- Use deterministic `check_order` values
- Start policy experiments as optional rules
- Promote to required only after false-positive review
- Include clear `hint` text for faster remediation

Custom rules docs: [Examples: Custom Rules](examples/custom_rules.md)

## Safety and trust model

Rules may inspect local files, source code, environment variables, executable presence, and importable modules.

!!! warning
    Only run trusted custom rules files, especially in shared CI environments.

## Related docs

- [Diagnostics](diagnostics.md)
- [Rule Inventory](rule_inventory.md)
- [Minimal Profile](minimal_profile.md)
- [Semver Policy](semver_policy.md)
