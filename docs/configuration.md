# Configuration

`azure-functions-doctor` configuration is primarily CLI-driven.

This page explains how runtime behavior changes with flags, profiles, formats, and custom rules.

## Command shape

```bash
azure-functions-doctor doctor [OPTIONS]
```

Core options:

- `--path <directory>` (default `.`)
- `--profile <minimal|deploy|development|full>`
- `--format <table|json|sarif|junit>`
- `--output <file>`
- `--summary-json <file>`
- `-v`, `--verbose`
- `--debug`
- `--rules <file>`
- `--target-python <version>`
- `--deployment-mode <remote-build|local|local-prebuilt|container>` (default `remote-build`)
- `--hosting-plan <linux-consumption|flex-consumption|premium|dedicated>`

## Target path configuration

By default, diagnostics run against the current directory.

```bash
azure-functions-doctor doctor
```

To check another project:

```bash
azure-functions-doctor doctor --path ./apps/orders-function
```

Path validation behavior:

- Path must exist
- Path must be a directory
- Path must be readable

If invalid, the CLI fails early with a parameter error.

## Profile selection

Profiles control which rules execute.

### `full` profile

- Includes required and optional rules
- Gives broader operational insight
- Best for local development and periodic quality sweeps

### `minimal` profile

- Includes only rules marked `required: true`
- Best for CI gates where noise must stay low
- Stable contract for pass/fail baseline

```bash
azure-functions-doctor doctor --profile minimal
```

### `deploy` profile

- Azure runtime, hosting, and deployment correctness (the core rule group minus
  local dev-environment checks)
- Best for a pre-deploy gate that runs where no venv or Core Tools exist

```bash
azure-functions-doctor doctor --profile deploy
```

### `development` profile

- Local dev-environment checks only: virtual environment, Python executable,
  Core Tools, `local.settings.json`
- Best for onboarding and workstation setup verification

```bash
azure-functions-doctor doctor --profile development
```

See [Minimal Profile](minimal_profile.md) for complete rule coverage.

## Output format configuration

### `table`

- Default human-readable output
- Best for local terminal use

### `json`

- Machine-readable object with `metadata` and `results`
- Best for CI parsing and automation

### `sarif`

- SARIF 2.1.0 document
- Best for code scanning ecosystems

### `junit`

- JUnit-style XML
- Best for CI test-report UIs

Example:

```bash
azure-functions-doctor doctor --format json --output artifacts/doctor.json
```

!!! note
    Current supported formats are `table`, `json`, `sarif`, and `junit`.

## Output file behavior

If `--output` is omitted, output is printed to stdout.

If `--output` is provided:

- Parent directory is created when needed
- File is overwritten with new report content
- CLI prints a success line showing destination path

Example:

```bash
azure-functions-doctor doctor --format sarif --output reports/doctor.sarif
```

## Verbose and debug modes

### `--verbose`

Shows fix hints for non-passing checks in table output.

```bash
azure-functions-doctor doctor --verbose
```

### `--debug`

Enables debug logging output for deeper troubleshooting.

```bash
azure-functions-doctor doctor --debug
```

Use debug mode when diagnosing tool behavior rather than project diagnostics.

## Custom rule set configuration

You can replace built-in rules with a custom file:

```bash
azure-functions-doctor doctor --rules ./rules/custom-v2.json
```

Behavior:

- The file must exist
- The file must be valid JSON
- The rule list must pass `rules.schema.json` validation
- Rules are sorted by `check_order`

See [Rules](rules.md) and [Examples: Custom Rules](examples/custom_rules.md).

## Summary file configuration

`--summary-json` writes a small counts-only document alongside whatever
`--format` produces. It is format-independent, and the parent directory is
created when needed.

```bash
azure-functions-doctor doctor --format table --summary-json artifacts/summary.json
```

The file contains the counts for the run, for example:

```json
{"passed": 23, "warned": 3, "failed": 0, "skipped": 15}
```

That is enough for a CI badge or a job summary without parsing the full report.

## Deployment mode configuration

`--deployment-mode` tells the dependency checks how the app's packages reach
Azure, so they stop reporting problems that do not apply to your pipeline.

| Value | Meaning |
| --- | --- |
| `remote-build` (default) | Azure builds dependencies from `requirements.txt` during deployment. |
| `local` / `local-prebuilt` | Dependencies are built or vendored locally and shipped with the package. |
| `container` | Dependencies are baked into a custom container image. |

```bash
azure-functions-doctor doctor --deployment-mode container
```

## Hosting plan configuration

`--hosting-plan` declares the Azure hosting plan you are targeting so that
Python-version validation matches the plan's real constraints.

| Value | Meaning |
| --- | --- |
| `linux-consumption` | Legacy Linux Consumption; caps at Python 3.12 and retires 30 September 2028. |
| `flex-consumption` | Flex Consumption, the recommended serverless plan. |
| `premium` | Elastic Premium plan. |
| `dedicated` | App Service (Dedicated) plan. |

```bash
azure-functions-doctor doctor --hosting-plan flex-consumption
```

Without this flag, Doctor infers the plan from infrastructure files (for example
a Bicep `functionAppConfig` block) when it can, and skips plan-specific version
caps when it cannot.

## Environment variables

Runtime behavior is CLI-driven. The only environment variable the tool reads is
`AZURE_FUNCTIONS_DOCTOR_LOG_LEVEL`, which sets the internal logging verbosity
(for example `DEBUG`, `INFO`, `WARNING`).

```bash
AZURE_FUNCTIONS_DOCTOR_LOG_LEVEL=DEBUG azure-functions-doctor doctor
```

All other configuration is expressed through the CLI options listed above.

## Recommended CI configuration

For merge blocking:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

Why this shape works well:

- Deterministic required-only checks
- Parse-friendly machine output
- Exit code directly indicates gate status

See [Examples: CI Integration](examples/ci_integration.md).

## Configuration anti-patterns

- Using full profile as hard gate for every PR (too noisy)
- Parsing display-only fields (such as section `title`) as contracts
- Assuming optional warnings fail builds
- Passing untrusted custom rules files in shared CI

## Related pages

- [Usage](usage.md)
- [Diagnostics](diagnostics.md)
- [JSON Output Contract](json_output_contract.md)
- [Troubleshooting](troubleshooting.md)
