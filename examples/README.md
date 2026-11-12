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

Each passing example includes:
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
| Unsupported Flex runtime | `examples/v2/broken-flex-runtime-config` | `check_flex_runtime_config` fails: python 3.9 is outside the supported 3.10-3.14 range |
| Deprecated Flex app settings | `examples/v2/broken-flex-deprecated-settings` | `check_flex_deprecated_settings` warns: `FUNCTIONS_WORKER_RUNTIME` and `SCM_DO_BUILD_DURING_DEPLOYMENT` are ignored on Flex |
| Flex deployment storage | `examples/v2/broken-flex-deployment-storage` | `check_flex_deployment_storage` warns: no container URL or authentication declared |
| Dev storage in deployable infra | `examples/v2/broken-dev-storage-leak` | `check_dev_storage_connection` warns: `UseDevelopmentStorage=true` in a Bicep template |
| Legacy extension version | `examples/v2/broken-legacy-extension-version` | `check_functions_extension_version` warns on the `~3` pin, and the runtime lifecycle check fails |

The Flex, dev-storage and extension-version examples read the files checked in beside them (`main.bicep`, `main.json`, `local.settings.json`), so a result describes what the project declares. It says nothing about the state of a deployed resource, and none of them needs an Azure subscription. Each example's own `README.md` explains its rule.

## Run Diagnostics

```bash
# Passing examples (all checks should pass)
azure-functions-doctor doctor --path examples/v2/http-trigger
azure-functions-doctor doctor --path examples/v2/timer-trigger
azure-functions-doctor doctor --path examples/v2/multi-trigger
azure-functions-doctor doctor --path examples/v2/blueprint
azure-functions-doctor doctor --path examples/v2/flex-consumption

# Broken examples (expect specific failures)
azure-functions-doctor doctor --path examples/v2/broken-missing-host-json
azure-functions-doctor doctor --path examples/v2/broken-missing-requirements
azure-functions-doctor doctor --path examples/v2/broken-missing-azure-functions
azure-functions-doctor doctor --path examples/v2/broken-no-v2-decorators
azure-functions-doctor doctor --path examples/v2/broken-flex-runtime-config
azure-functions-doctor doctor --path examples/v2/broken-flex-deprecated-settings
azure-functions-doctor doctor --path examples/v2/broken-flex-deployment-storage
azure-functions-doctor doctor --path examples/v2/broken-dev-storage-leak
azure-functions-doctor doctor --path examples/v2/broken-legacy-extension-version
```
