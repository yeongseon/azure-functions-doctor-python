# Linux runtime (linuxFxVersion)

> Rule ID: `check_linux_fx_version` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full`

## What it checks

Any Python `linuxFxVersion` declared in **infra config** (bicep/ARM, including nested `infra/` directories). Doctor recognizes Python 3.10–3.14 for analysis. Lifecycle support and hosting-plan compatibility are evaluated separately. Infra files are scanned for `linuxFxVersion` declarations such as `linuxFxVersion: 'Python|3.12'`; no declaration skips.

## Why it matters

An unsupported Python runtime encoded in `linuxFxVersion` causes deployment or cold-start failures on Linux Consumption, Flex Consumption, Premium, and Dedicated plans.

## Symptoms

Deployment fails; app stuck in a restart loop; "runtime not supported" errors in the platform logs.

## Example finding

```text
Unsupported Python linuxFxVersion runtime(s) in infra config:
- main.bicep: Python|3.9

Fix: target a recognized Python runtime (3.10–3.14).
```

## How to fix

Set `linuxFxVersion` to a recognized Python runtime (e.g. `Python|3.12`) in your infrastructure templates. Review the lifecycle and hosting-plan findings separately to confirm that the selected target remains supported for deployment.

## Reference

- [Azure Functions Python developer guide — Supported Python versions](https://learn.microsoft.com/azure/azure-functions/functions-reference-python#supported-python-versions)
- On Flex Consumption, `linuxFxVersion` is ignored — see [`check_flex_runtime_config`](check_flex_runtime_config.md)
