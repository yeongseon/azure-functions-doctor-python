# Hosting plan lifecycle

> Rule ID: `check_hosting_plan_lifecycle` · Category: configuration · Section: runtime
> Severity: info (distant), warning (retiring soon), error (retired) · Profiles: `deploy`, `full` · Tier: core

## What it checks

The resolved hosting plan against its **published retirement date**. The plan is resolved from infra config (bicep/ARM) and deploy-config ingestion; dates come from the compatibility catalog.

| Plan state | Status |
| --- | --- |
| Retirement far away | `pass` (info) |
| Inside the retiring-soon window | `warn` |
| Already retired | `fail` |
| Plan undeterminable | `skip` |

## Why it matters

Hosting plans retire on a published schedule; an app left on a retiring plan must eventually migrate or stop running.

## Symptoms

Apps on a retiring hosting plan keep running until the retirement date, then must migrate; migrations left too late force a rushed move.

## Example finding

```text
The 'linux-consumption' hosting plan is supported; it retires on September 30, 2028.
Consider Flex Consumption for new workloads.
```

The finding carries auditable evidence (Finding Contract v2): `expected`, `actual`, `source_url`, `last_verified`, and `catalog_version`.

## How to fix

Linux Consumption is retiring; consider Flex Consumption for new Python workloads. See the [plan choosing guide](../choose-a-plan.md) for the decision matrix.

## Reference

- [Azure Functions — Migrate Consumption to Flex Consumption](https://learn.microsoft.com/azure/azure-functions/migrate-plan-consumption-to-flex)
