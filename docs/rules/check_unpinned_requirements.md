# Pinned requirements

> Rule ID: `check_unpinned_requirements` · Category: dependencies · Section: dependencies
> Severity: warning (non-gating) · Profiles: `deploy`, `full`

## What it checks

`requirements.txt` for dependencies declared with **no version specifier** or an **unbounded lower bound** (`>=` without an upper bound).

## Why it matters

Azure remote build resolves `requirements.txt` at deploy time; unpinned dependencies let a new upstream release change or break a deployment without any code change.

## Symptoms

A deployment that previously worked suddenly fails or behaves differently; irreproducible builds across environments.

## Example finding

```text
Unpinned or unbounded dependencies in requirements.txt:
- azure-functions (no version specifier)
- requests (>=2.0; no upper bound)

Fix: pin versions (e.g. 'package==1.2.3') or add an upper bound to keep
deployments reproducible.
```

## How to fix

Pin dependency versions (e.g. `package==1.2.3`) or add an upper bound to keep deployments reproducible.

## Reference

- [Azure Functions Python developer guide — Package management](https://learn.microsoft.com/azure/azure-functions/functions-reference-python#package-management)
