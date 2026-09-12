# Functions extension version

> Rule ID: `check_functions_extension_version` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full`

## What it checks

`FUNCTIONS_EXTENSION_VERSION` in `local.settings.json`. A missing, legacy (`~1`/`~2`/`~3`), or otherwise non-`~4` value is flagged so the app targets the supported v4 Azure Functions runtime. Flex Consumption apps skip — on Flex the runtime is owned by [`check_flex_runtime_config`](check_flex_runtime_config.md) via `functionAppConfig.runtime`.

## Why it matters

Legacy Azure Functions runtimes (`~1`/`~2`/`~3`) are retired; deploying against them causes host startup failures and unsupported-runtime errors.

## Symptoms

Host fails to start; deployment rejected with unsupported runtime version; functions never come online.

## Example findings

Missing value:

```text
FUNCTIONS_EXTENSION_VERSION is not set in local.settings.json;
pin it to '~4' for the current Azure Functions runtime.
```

Legacy value:

```text
FUNCTIONS_EXTENSION_VERSION is '~3', expected '~4'. Legacy runtimes
(~1/~2/~3) are retired; target the v4 runtime.
```

## How to fix

Set `FUNCTIONS_EXTENSION_VERSION` to `~4` in `local.settings.json`; the v1/v2/v3 runtimes are retired.

## Reference

- [Azure Functions runtime versions overview](https://learn.microsoft.com/azure/azure-functions/functions-versions)
- Related rule: [`check_functions_runtime_lifecycle`](check_functions_runtime_lifecycle.md) applies the catalog's lifecycle dates to the resolved runtime
