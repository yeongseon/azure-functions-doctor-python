# Dev-storage emulator connection

> Rule ID: `check_dev_storage_connection` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full`

## What it checks

`AzureWebJobsStorage=UseDevelopmentStorage=true` in **deployable infra config** (bicep/ARM). That value points at the local Azurite emulator and must never ship to a deployed app. The same value in `local.settings.json` is fine — only deployable templates are flagged.

## Why it matters

The dev-storage emulator connection is unreachable from Azure; shipping it in provisioned app settings makes the deployed Functions host fail to start.

## Symptoms

Deployed app fails health checks; host cannot reach storage; triggers never fire in the cloud.

## Example finding

```text
Dev-storage emulator connection in deployable config (ships to production):
- main.bicep

Fix: provision a real storage account connection for AzureWebJobsStorage in
deployment templates; keep UseDevelopmentStorage=true only in local.settings.json.
```

## How to fix

Provision a real storage account connection for `AzureWebJobsStorage` in deployment templates; keep `UseDevelopmentStorage=true` only in `local.settings.json`.

## Reference

- [App settings reference — AzureWebJobsStorage](https://learn.microsoft.com/azure/azure-functions/functions-app-settings#azurewebjobsstorage)
