# Functions runtime lifecycle

> Rule ID: `check_functions_runtime_lifecycle` · Category: configuration · Section: runtime
> Severity: error (gating) on v1/v2/v3 · Profiles: `deploy`, `full` · Tier: core

## What it checks

The Azure Functions runtime major version (`FUNCTIONS_EXTENSION_VERSION`) for a Python app:

| Runtime | Verdict |
| --- | --- |
| v1 | Incompatible with Python — fails outright |
| v2 / v3 | Out of support — fails |
| v3 on Linux Consumption | Out of support **and** stops running on a published date — emphasized failure |
| v4 | Current GA runtime — passes |
| Undeterminable | Skips |

The runtime is resolved from infra config / app settings via the deploy-config ingestion pipeline; lifecycle dates come from the version-controlled compatibility catalog.

## Why it matters

Running on a legacy or out-of-support Azure Functions runtime loses security updates and eventually the ability to run; runtime v1 cannot host a Python app at all.

## Symptoms

Host fails to start on an unsupported runtime; v3 Linux Consumption apps stop running after the published date; v1 rejects Python apps outright.

## Example finding

```text
Azure Functions runtime v3 is out of support; migrate to runtime v4.
```

## How to fix

Target the v4 Azure Functions runtime (`FUNCTIONS_EXTENSION_VERSION=~4`). The v1/v2/v3 runtimes are legacy or out of support; v1 does not support Python at all.

## Reference

- [Azure Functions — Compare runtime versions](https://learn.microsoft.com/azure/azure-functions/functions-versions)
- Related rule: [`check_functions_extension_version`](check_functions_extension_version.md) validates the value declared in `local.settings.json`
