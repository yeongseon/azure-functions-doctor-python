# Rule Stability and Semver Policy

This document defines how built-in rules evolve over time so that users can rely on Azure Functions Doctor in both local and CI workflows.

## Rule States

Every built-in rule has one of three stability states:

| State | Meaning |
| --- | --- |
| **Stable** | Fully supported. False positives are treated as bugs. |
| **Experimental** | Under evaluation. May change behavior or be removed in a minor release. False positives are documented as known limitations. |
| **Deprecated** | Scheduled for removal. Announced in the changelog and removed in the next major release. |

All 41 current built-in rules are **stable**.

## State Transitions

- **Experimental to Stable**: Requires test coverage and at least one minor release cycle without breaking changes.
- **Stable to Deprecated**: Announced in the changelog. The rule continues to run until the next major release.
- **Deprecated to Removed**: Occurs only in a major release.

## Versioning Impact

| Change | Version Bump |
| --- | --- |
| Add an optional rule to the `full` profile | Minor |
| Add a required rule to the `minimal` profile | **Major** (breaking) |
| Change the meaning of a required rule | **Major** (breaking) |
| Change the meaning of an optional rule | Minor |
| Remove a deprecated rule | **Major** |
| Fix a false positive in a stable rule | Patch |
| Add an experimental rule | Minor |
| Change or remove an experimental rule | Minor |
| Escalate a rule's behavior (warning to runtime error) | **Minor** (at least) |

## Behavior Escalation Policy

A **behavior escalation** is any change that tightens how existing, previously accepted usage is treated at runtime — most commonly turning a `warning` into a hard runtime error, but also any equivalent tightening (e.g. promoting an advisory into a failing check for input that used to pass).

Such a change **breaks callers whose code ran cleanly before**, so it must never ship in a patch release:

- A behavior escalation requires **at least a minor version bump** — never a patch.
- It requires a **CHANGELOG migration note** describing the old behavior, the new behavior, and how to adapt (or opt out).
- This rule applies **toolkit-wide**, not just to Azure Functions Doctor. Doctor owns the toolkit's semver/stability convention, so sibling packages should reference this policy. (Follow-up: link it from the DX hub and sibling `CONTRIBUTING` files.)

**Motivating example.** `azure-functions-validation` **0.11.1** — a *patch* release — escalated a decorator warning into a `RuntimeError`:

- `0.9.0`: *(decorator)* warn when `@validate_http` is applied above `@with_context` (#278).
- `0.11.1`: *(decorator)* raise `RuntimeError` when `@validate_http` wraps a `FunctionBuilder` (#299).

Code that emitted only a warning under `0.9.0`–`0.11.0` began raising at import/registration time on the `0.11.1` patch, with no migration note. Under this policy that escalation would have required at least a `0.12.0` minor bump and a CHANGELOG migration note.

> Enforcement note: an automated doctor check that flags escalation-on-patch is tracked separately and intentionally out of scope here.

## Profile Change Policy

The `minimal` profile runs only rules marked `required: true`. Because CI pipelines depend on minimal producing a stable, predictable set of checks:

- Adding a rule to `minimal` (marking it `required: true`) is a **breaking change** and requires a major version bump.
- Adding optional rules to `full` is a minor change.
- Removing an optional rule from `full` follows the deprecation path above.

## False-positive Handling

- **Stable rules**: False positives are bugs. They are fixed in patch releases.
- **Experimental rules**: False positives are documented as known limitations in the rule description or changelog.
- **Deprecated rules**: False positives are not fixed; users should migrate away.

## Current Rule Status

All 41 rules in `v2.json` are **stable**. See the [Rule Inventory](rule_inventory.md) for the complete list.
