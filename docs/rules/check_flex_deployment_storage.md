# Flex Consumption deployment storage

> Rule ID: `check_flex_deployment_storage` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full` · Tier: core

## What it checks

For a **Flex Consumption** app, the deployment storage shape declared under `functionAppConfig.deployment.storage`:

- A **container URL** (`value`) must be specified.
- **Authentication** must be configured — a managed identity or a named storage account connection string (`storageAccountConnectionStringName`).

A Flex app whose infra declares no deployment storage block skips gracefully (the block may be managed elsewhere). This is a static shape check only; the storage account is never contacted. Non-Flex apps skip.

## Why it matters

Flex Consumption deploys from a blob container declared under `functionAppConfig.deployment.storage`; a missing container or unconfigured authentication produces a deployment that cannot fetch its package.

## Symptoms

A Flex app with no deployment container or no authentication configured fails to deploy or cannot fetch its package at scale-out.

## Example finding

```text
Flex Consumption deployment storage is misconfigured:
  - no deployment container is specified
    (functionAppConfig.deployment.storage.value)
  - no authentication is configured; use a managed identity or a storage
    account connection string
Declare a blob container under functionAppConfig.deployment.storage with
a value URL and authentication (managed identity or connection string).
```

## How to fix

Declare a blob container under `functionAppConfig.deployment.storage` with a `value` URL and authentication (managed identity or a named connection string).

## Reference

- [Azure Functions — Flex Consumption plan (`functionAppConfig.deployment.storage`)](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
