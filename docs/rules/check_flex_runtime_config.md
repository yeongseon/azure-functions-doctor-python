# Flex Consumption runtime config

> Rule ID: `check_flex_runtime_config` · Category: configuration · Section: runtime
> Severity: error (gating) on an unsupported runtime, warning on a legacy `linuxFxVersion` · Profiles: `deploy`, `full` · Tier: core

## What it checks

For a **Flex Consumption** app, the runtime declared under `functionAppConfig.runtime` (`name`/`version`):

- A non-Python or undeclared runtime **skips**.
- An unsupported Python version **fails** against the Flex hosting-plan matrix (Flex supports Python 3.10–3.14).
- A legacy `linuxFxVersion` declaration **warns** — Flex ignores it.

Non-Flex apps skip.

## Why it matters

Flex Consumption resolves its runtime from `functionAppConfig.runtime` and ignores `linuxFxVersion`; a misdeclared or unsupported runtime version fails to deploy or run.

## Symptoms

A Flex app with only `linuxFxVersion` set has no effective runtime declaration; an unsupported Python version is rejected at deploy time.

## Example findings

Unsupported runtime version:

```text
Flex Consumption runtime Python 3.9 is not supported; target a supported
Python runtime (3.10–3.14).
```

Legacy `linuxFxVersion` on a Flex app:

```text
linuxFxVersion is declared on a Flex Consumption app, which ignores it;
declare the runtime under functionAppConfig.runtime (name/version) instead.
```

## How to fix

Declare the Flex Consumption runtime under `functionAppConfig.runtime` (`name`/`version`); do not use `linuxFxVersion`.

## Reference

- [Azure Functions — Flex Consumption plan (`functionAppConfig.runtime`)](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
