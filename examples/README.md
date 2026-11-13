# Examples

Azure Functions Doctor ships with examples for the **Azure Functions Python v2 programming model**.

## Passing Examples

| Example | Path | Description |
| --- | --- | --- |
| HTTP trigger | `examples/v2/http-trigger` | Minimal HTTP trigger — all checks pass. |
| Timer trigger | `examples/v2/timer-trigger` | Timer trigger with 5-minute CRON schedule. |
| Multi-trigger | `examples/v2/multi-trigger` | HTTP + Timer + Queue triggers in one app. |
| Blueprint | `examples/v2/blueprint` | Modular app using `func.Blueprint`. |
| Flex Consumption | `examples/v2/flex-consumption` | Healthy Flex Consumption app: runtime config, app settings, deployment storage and dev-storage checks all pass. |

The HTTP, timer, multi-trigger and blueprint examples each include (the Flex Consumption example is leaner: no `.funcignore` or `.gitignore`, and it adds `main.json`):
- `function_app.py` — v2 decorator-based trigger(s)
- `host.json` — extensionBundle v4
- `requirements.txt`
- `local.settings.sample.json` — safe to commit; copy to `local.settings.json` before running
- `.funcignore` — excludes `.venv`, `__pycache__`, `local.settings.json`, etc.
- `.gitignore`

## Broken Examples

Intentionally misconfigured projects that demonstrate specific rule failures.

| Example | Path | Expected failure |
| --- | --- | --- |
| Missing host.json | `examples/v2/broken-missing-host-json` | `check_host_json` |
| Missing requirements.txt | `examples/v2/broken-missing-requirements` | `check_requirements_txt` |
| Missing azure-functions | `examples/v2/broken-missing-azure-functions` | `check_azure_functions_library` |
| No v2 decorators | `examples/v2/broken-no-v2-decorators` | `programming_model` fail-fast detection |
| Validation integration | `examples/v2/validation-integration` | Located decorator-order and endpoint-metadata warnings |
| Unbounded native requirements | `examples/v2/warn-unbound-requirements` | Located unpinned requirement and native dependency warnings |
| Unsupported Linux runtime | `examples/v2/broken-linux-fx-version` | `check_linux_fx_version` in Bicep |
| Unresolved binding connection | `examples/v2/broken-unresolved-connection` | Located `check_binding_connection_resolution` warning |
| Nondeterministic orchestrator | `examples/v2/warn-nondeterministic-orchestrator` | Located `check_durable_nondeterminism` failure |
| Dev-storage emulator in infra | `examples/v2/broken-dev-storage-leak` | `check_dev_storage_connection` (warn): `UseDevelopmentStorage=true` in `main.bicep` |
| Flex deployment storage | `examples/v2/broken-flex-deployment-storage` | `check_flex_deployment_storage` (warn): no container or auth declared |
| Flex deprecated settings | `examples/v2/broken-flex-deprecated-settings` | `check_flex_deprecated_settings` (warn): legacy app settings declared |
| Flex unsupported runtime | `examples/v2/broken-flex-runtime-config` | `check_flex_runtime_config` (fail): python 3.9 is outside the supported 3.10-3.14 range |
| Legacy extension version | `examples/v2/broken-legacy-extension-version` | `check_functions_extension_version` (warn) on the `~3` pin; the runtime lifecycle check also fails |
| pyproject-only dependencies | `examples/v2/pyproject-only-dependencies` | `check_requirements_txt` and `check_azure_functions_library` fail under `remote-build`, pass under `--deployment-mode local` |

## Run Diagnostics

```bash
# Passing examples (all checks should pass)
azure-functions-doctor doctor --path examples/v2/http-trigger
azure-functions-doctor doctor --path examples/v2/timer-trigger
azure-functions-doctor doctor --path examples/v2/multi-trigger
azure-functions-doctor doctor --path examples/v2/blueprint
azure-functions-doctor doctor --path examples/v2/flex-consumption --profile deploy

# Broken examples (expect specific failures)
azure-functions-doctor doctor --path examples/v2/broken-missing-host-json
azure-functions-doctor doctor --path examples/v2/broken-missing-requirements
azure-functions-doctor doctor --path examples/v2/broken-missing-azure-functions
azure-functions-doctor doctor --path examples/v2/broken-no-v2-decorators

# Flex Consumption, dev-storage and extension-version examples (static infra/config checks)
azure-functions-doctor doctor --path examples/v2/broken-dev-storage-leak
azure-functions-doctor doctor --path examples/v2/broken-flex-deployment-storage
azure-functions-doctor doctor --path examples/v2/broken-flex-deprecated-settings
azure-functions-doctor doctor --path examples/v2/broken-flex-runtime-config
azure-functions-doctor doctor --path examples/v2/broken-legacy-extension-version
```

### Warnings versus failures in the Flex and storage examples

These examples are read-only: Doctor parses the checked-in `main.bicep` /
`main.json` and `local.settings.json` files. It never contacts Azure, so none of
the findings (and none of these examples needs an Azure subscription) means a real resource failed or was misconfigured in a subscription.
Each finding describes configuration the template *declares*.

- `(warn)` rows are optional-rule warnings about declared configuration; the
  command still exits `0`.
- `check_flex_runtime_config` is a required-rule `fail` for the declared
  runtime (python 3.9); it makes the command exit `1`.
- `broken-legacy-extension-version` also fails the runtime lifecycle check, because
  the `~3` runtime is past end-of-support; that makes the command exit `1`. Each
  example's own `README.md` explains its rule.
- Other warnings in the output (for example `check_venv`, `check_app_insights`,
  `.funcignore`, `local.settings.json` git tracking) depend on your machine and
  checkout and are not what these examples demonstrate.

`tests/test_examples_index.py` verifies that every `(warn)`/`(fail)` row above
matches the status Doctor reports for that rule on the fixture, and
`tests/test_examples_readme_index.py` verifies that every directory under
`examples/v2` is listed here and that each Flex, dev-storage and
extension-version row names the same rule as the example's own README.
