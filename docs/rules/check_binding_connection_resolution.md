# Binding connection resolution

> Rule ID: `check_binding_connection_resolution` · Category: configuration · Section: runtime
> Severity: warning (non-gating) · Profiles: `deploy`, `full` · Tier: core

## What it checks

`connection=` references in v2 trigger/binding decorators — Storage, Service Bus, Event Hub, Cosmos DB, and any binding exposing a `connection` keyword — and resolves each against:

1. `local.settings.json` `Values`, and
2. app settings ingested from deploy config (infra bicep/ARM).

A referenced connection with no corresponding configuration warns. **Identity-based connection groups** (`<name>__serviceUri`, `<name>__accountName`, …) are treated as configured.

## Why it matters

A trigger or binding that references `connection="Name"` fails to bind at runtime when no matching app setting or identity-based connection group is configured; catching this before deploy avoids a cold-start failure discovered only in production logs.

## Symptoms

A binding references a connection name that has no corresponding app setting, so the function fails to start or the trigger never fires after deployment.

## Example finding

```text
Binding connections reference unconfigured settings:
  - MyStorage (function_app.py:work)
Add the missing app setting(s), or configure an identity-based connection
group (<name>__serviceUri / <name>__accountName).
```

## How to fix

Add the missing app setting for each referenced connection, or configure an identity-based connection group (`<name>__serviceUri` / `<name>__accountName`).

## Reference

- [Azure Functions — Connections (binding connection resolution)](https://learn.microsoft.com/azure/azure-functions/functions-reference#connections)
