# FAQ

## What does Azure Functions Doctor check?

It checks project readiness for Azure Functions Python v2 apps, including:

- Required runtime and structure checks (Python version, `host.json`, `requirements.txt`)
- Dependency declaration checks (for example `azure-functions` in `requirements.txt`)
- Optional operational checks (Core Tools, telemetry, extension bundle, cleanup patterns)

See [Rule Inventory](rule_inventory.md) for the complete built-in list.

## How do I run it quickly?

```bash
azure-functions-doctor doctor
```

Run against a different directory:

```bash
azure-functions-doctor doctor --path ./my-function-app
```

## How do I use it in CI?

Use required-only profile plus JSON output:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

Then:

- Use exit code for pass/fail gating
- Publish `doctor.json` as build artifact
- Optionally parse required failures for richer PR comments

See [Examples: CI Integration](examples/ci_integration.md).

## Can I ignore specific rules?

There is no built-in per-rule ignore flag in the current CLI.

Current options:

- Use `--profile minimal` to run only required rules
- Provide a custom `--rules` file that excludes or adjusts specific rules

## What is the minimal profile?

`--profile minimal` runs only rules where `required: true` in the active ruleset.

This profile is designed for stable, low-noise CI gating.

See [Minimal Profile](minimal_profile.md).

## What output formats are supported?

- `table` (default)
- `json`
- `sarif`
- `junit`

Example:

```bash
azure-functions-doctor doctor --format sarif --output doctor.sarif
```

## Is Markdown output supported?

Not as a direct CLI format today. Use JSON output and render Markdown in your own pipeline if needed.

## What is the JSON output contract?

JSON output contains:

- `metadata`: run metadata (`tool_version`, `generated_at`, `target_path`)
- `results`: section and item-level diagnostics with statuses

Contract details are documented in [JSON Output Contract](json_output_contract.md).

## Which Python versions are supported?

The package requires Python `>=3.10,<3.15`.

See [Supported Versions](supported_versions.md).

## Does the doctor modify my project?

No. It is a read-only diagnostic tool. It inspects files, environment variables, and local tooling signals.

## Why did my run fail even with many passes?

Any required failure returns exit code `1`, even if most checks pass.

Look for:

- Item status `fail` (required)
- Summary line counts
- Verbose hints (`--verbose`) for exact fix suggestions

## Why do I see warnings (`warn`) in full profile?

Warnings represent optional checks that failed. They do not fail required gate status by themselves.

## How do I add custom rules?

1. Start from built-in schema shape
2. Define rule objects with valid `type`, `condition`, `required`, and `check_order`
3. Run with `--rules <path>`

See [Rules](rules.md) and [Examples: Custom Rules](examples/custom_rules.md).

## What happens if my custom rules file is invalid?

The run fails before execution with a validation error. Rules are validated against:

`src/azure_functions_doctor/schemas/rules.schema.json`

## Can I use the doctor from Python code?

Yes. Use the public API:

```python
from azure_functions_doctor.api import run_diagnostics

results = run_diagnostics(path=".", profile="minimal", rules_path=None)
```

See [API Reference](api.md).

## Why does the v2 programming model check fail?

The rule looks for decorator-style usage (`@app.`) in Python source AST.

If your app is v1-style or uses non-standard patterns, this check can fail.

## Is Azure Functions Core Tools required?

Not by the doctor itself. Core Tools checks are optional in the built-in ruleset.

## I only want hard blockers in CI. What is the safest setup?

Use:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

That gives:

- Stable required-only check scope
- Reliable exit-code gating
- Machine-readable artifact for debugging

## Where should I report false positives?

Open an issue in the repository with:

- Tool version
- Project layout or minimal reproducible sample
- Full command used
- Output snippet (prefer JSON)

See [Troubleshooting](troubleshooting.md) for reporting guidance.
