# Flex Consumption deprecated app settings

> Rule ID: `check_flex_deprecated_settings` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full` · Tier: core

## What it checks

For a **Flex Consumption** app, whether legacy app settings that Flex **ignores** are declared. Each flagged setting cites its replacement mechanism:

| Deprecated setting | Replacement |
| --- | --- |
| `FUNCTIONS_WORKER_RUNTIME` | `name` under `functionAppConfig.runtime` |
| `FUNCTIONS_WORKER_RUNTIME_VERSION` | `version` under `functionAppConfig.runtime` |
| `FUNCTIONS_WORKER_PROCESS_COUNT` | Not valid on Flex; per-instance concurrency is platform-managed |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `remoteBuild` parameter when deploying to Flex |
| `ENABLE_ORYX_BUILD` | `remoteBuild` parameter when deploying to Flex |
| `WEBSITE_CONTENTSHARE` | `functionAppConfig`'s deployment section |
| `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING` | `functionAppConfig`'s deployment section |
| `WEBSITE_RUN_FROM_PACKAGE` and VNet route-all settings | Site networking properties |

`linuxFxVersion` and `FUNCTIONS_EXTENSION_VERSION` are owned by [`check_flex_runtime_config`](check_flex_runtime_config.md) and [`check_functions_extension_version`](check_functions_extension_version.md) respectively, so this rule never emits a duplicate finding for them. Non-Flex apps skip.

## Why it matters

Flex Consumption ignores a set of legacy app settings; leaving them in place is a configuration smell that masks the correct `functionAppConfig`-based configuration and can confuse deployments.

## Symptoms

Deprecated app settings are silently ignored on Flex Consumption, so settings such as `FUNCTIONS_WORKER_RUNTIME` or `WEBSITE_RUN_FROM_PACKAGE` have no effect and hide the real configuration.

## Example finding

```text
Deprecated app settings declared on a Flex Consumption app:
  - FUNCTIONS_WORKER_RUNTIME: replaced by 'name' under functionAppConfig.runtime.
  - SCM_DO_BUILD_DURING_DEPLOYMENT: replaced by the remoteBuild parameter
    when deploying to Flex Consumption.
Flex Consumption ignores these settings; remove them and use the listed
replacement mechanism.
```

## How to fix

Remove legacy app settings on Flex Consumption; configure the runtime, deployment, scaling, and networking through `functionAppConfig` and site networking properties instead.

## Reference

- [Azure Functions — App settings reference (Flex Consumption plan deprecations)](https://learn.microsoft.com/azure/azure-functions/functions-app-settings)
