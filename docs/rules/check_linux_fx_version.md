# Linux runtime (linuxFxVersion)

> Rule ID: `check_linux_fx_version` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full`

## What it checks

Any Python `linuxFxVersion` declared in **infra config** (bicep/ARM, including nested `infra/` directories), so Flex Consumption / Linux plan apps target a supported Python runtime. Infra files are scanned for `linuxFxVersion` declarations such as `linuxFxVersion: 'Python|3.12'`; no declaration skips.

## Why it matters

An unsupported Python runtime encoded in `linuxFxVersion` causes deployment or cold-start failures on Linux Consumption, Flex Consumption, Premium, and Dedicated plans.

## Symptoms

Deployment fails; app stuck in a restart loop; "runtime not supported" errors in the platform logs.

## Example finding

```text
```text
Unsupported Python linuxFxVersion runtime(s) in infra config:
- main.bicep: Python|3.9

Fix: target a supported Python runtime (3.10–3.14).
```

## How to fix

Set `linuxFxVersion` to a supported Python runtime (e.g. `Python|3.12`) in your infrastructure templates.

## Reference

- [Azure Functions Python developer guide — Supported Python versions](https://learn.microsoft.com/azure/azure-functions/functions-reference-python#supported-python-versions)
- On Flex Consumption, `linuxFxVersion` is ignored — see [`check_flex_runtime_config`](check_flex_runtime_config.md)
