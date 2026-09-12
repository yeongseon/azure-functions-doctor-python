# Minimal Profile

`--profile minimal` runs only rules marked `required: true`.

This profile is designed for low-noise, deterministic CI gates.

## Why minimal exists

Full diagnostics are useful during development, but CI gate checks often need a smaller, stable baseline.

Minimal profile provides:

- clear blocker signal
- fewer environment-specific warnings
- predictable behavior across teams

## How minimal is selected

Rule inclusion logic:

- Load active ruleset (built-in or custom)
- Keep only rules where `required` is `true`
- Execute filtered set in normal section grouping

This means `minimal` behavior adapts to your custom rules file if you provide one.

## Built-in minimal rule set (current)

With built-in `v2.json`, minimal includes these 6 checks:

1. `check_python_version`
2. `check_requirements_txt`
3. `check_azure_functions_library`
4. `check_host_json`
5. `check_host_json_version`
6. `check_durable_nondeterminism`

These represent the minimum structural requirements for a valid Azure Functions Python v2 project.

## Full vs minimal comparison

| Dimension | `full` profile | `minimal` profile |
| --- | --- | --- |
| Rule scope | Required + optional | Required only |
| Built-in count | 41 rules | 6 rules |
| Warning volume | Higher | Lower |
| CI suitability | Useful for report artifacts | Best for hard gating |
| Local guidance depth | High | Baseline only |

## What minimal excludes (built-in)

Optional checks excluded by default include:

- Programming model v2 detection (`check_programming_model_v2`)
- Virtual environment activation (`check_venv`)
- Python executable path (`check_python_executable`)
- `azure-functions-worker` pin warning
- `local.settings.json` presence
- Core Tools availability/version
- Durable host config checks
- Application Insights signal checks
- `extensionBundle` host property
- ASGI/WSGI callable heuristics
- Cleanup pattern checks
- `.funcignore` presence
- `local.settings.json` git-tracking check
- Extension bundle v4 recommendation
These remain available in full profile.

## Command examples

Local blocker-only check:

```bash
azure-functions-doctor doctor --profile minimal
```

CI-friendly JSON artifact:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

Path-targeted monorepo check:

```bash
azure-functions-doctor doctor --path ./apps/orders-function --profile minimal
```

## Exit code behavior in minimal

Same as full profile:

- exit `0` when no required failures
- exit `1` when any required failure exists

Because minimal excludes optional checks, status interpretation is often simpler for gate logic.

## When to use minimal

Use minimal when you need:

- strict merge/deploy blockers
- stable cross-team CI baseline
- fewer false alarms from optional environment checks

Use full profile when you need broader local quality insights.

## Recommended team policy

Practical pattern:

1. CI gate uses `minimal` (required only)
2. Local dev uses `full --verbose` for richer guidance
3. Scheduled quality workflows collect full profile artifacts

This keeps enforcement stable while still exposing optional improvement areas.

## Minimal profile and semver

Adding a new required built-in rule changes minimal profile scope.

Per project semver policy, that is treated as a breaking change because it can fail previously passing CI pipelines.

Reference: [Semver Policy](semver_policy.md)

## Custom rules and minimal

If you supply `--rules custom.json`, minimal profile still means:

"Run only rules with `required: true` in that custom file."

This allows organization-specific baseline policies while preserving minimal semantics.

## Common misunderstandings

### "Minimal means fast only"

Minimal is not only about speed. Its main purpose is **stable, required-only policy enforcement**.

### "Warnings fail minimal"

Warnings are optional-rule failures. In built-in minimal profile, optional rules are excluded, so warnings are typically reduced or absent.

### "Minimal bypasses model checks"

It does not. The v2 programming model rule is optional (`required: false`) and not included in built-in minimal.

## Related docs

- [Usage](usage.md)
- [Diagnostics](diagnostics.md)
- [Rule Inventory](rule_inventory.md)
- [Examples: CI Integration](examples/ci_integration.md)
