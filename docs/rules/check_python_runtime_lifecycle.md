# Python runtime lifecycle

> Rule ID: `check_python_runtime_lifecycle` · Category: environment · Section: python_env
> Severity: warning inside the retiring window, error past end-of-support · Profiles: `deploy`, `full` · Tier: core

## What it checks

The target Python version against its **published Azure Functions end-of-support date**. The check warns when the target runtime is retiring and fails once it is past end-of-support.

The target version is resolved the same way as [`check_python_version`](../rules.md#3-check_python_version): `--target-python` override, then `.python-version`, then the interpreter running Doctor.

## Why it matters

Azure Functions retires Python runtimes on a published schedule. Deploying on a runtime at or past end-of-support risks losing security updates and, eventually, the ability to deploy at all.

## Symptoms

Deployments on a retiring runtime keep working until the end-of-support date, then fail or lose patching; upgrades left too late force a rushed migration.

## Example finding

```text
Python 3.10.12 is past Azure Functions end-of-support (ended October 2026);
upgrade to a newer supported Python (e.g. 3.14).
```

The finding carries auditable evidence (Finding Contract v2): `expected`, `actual`, `source_url`, `last_verified`, and `catalog_version` from the version-controlled compatibility catalog.

## How to fix

Target a Python version with a long support runway (3.12+). Python 3.10 remains
analyzable by Doctor but is end-of-support; Python 3.14 is GA.

## Reference

- [Azure Functions — Supported languages (Python runtime lifecycle)](https://learn.microsoft.com/azure/azure-functions/supported-languages)
