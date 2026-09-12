# Examples

Azure Functions Doctor ships with examples for the **Azure Functions Python v2 programming model**.

## Passing Examples

| Example | Path | Description |
| --- | --- | --- |
| HTTP trigger | `examples/v2/http-trigger` | Minimal HTTP trigger — all checks pass. |
| Timer trigger | `examples/v2/timer-trigger` | Timer trigger with 5-minute CRON schedule. |
| Multi-trigger | `examples/v2/multi-trigger` | HTTP + Timer + Queue triggers in one app. |
| Blueprint | `examples/v2/blueprint` | Modular app using `func.Blueprint`. |

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

## Run Diagnostics

```bash
# Passing examples (all checks should pass)
azure-functions-doctor doctor --path examples/v2/http-trigger
azure-functions-doctor doctor --path examples/v2/timer-trigger
azure-functions-doctor doctor --path examples/v2/multi-trigger
azure-functions-doctor doctor --path examples/v2/blueprint

# Broken examples (expect specific failures)
azure-functions-doctor doctor --path examples/v2/broken-missing-host-json
azure-functions-doctor doctor --path examples/v2/broken-missing-requirements
azure-functions-doctor doctor --path examples/v2/broken-missing-azure-functions
azure-functions-doctor doctor --path examples/v2/broken-no-v2-decorators
```
