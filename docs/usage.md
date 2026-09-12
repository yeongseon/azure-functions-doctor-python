# CLI Usage

`azure-functions-doctor doctor` validates Azure Functions Python v2 projects and reports required failures versus optional warnings.

This page is the complete command and workflow reference.

## Command summary

```bash
azure-functions-doctor doctor [OPTIONS]
```

The command supports human-readable and machine-readable workflows:

- local developer loops (`table` output)
- CI gates (`json` + exit code)
- security/code-scanning pipelines (`sarif`)
- test-report ecosystems (`junit`)

## Quick examples

Current directory:

```bash
azure-functions-doctor doctor
```

Specific path:

```bash
azure-functions-doctor doctor --path ./apps/orders-function
```

Required-only profile:

```bash
azure-functions-doctor doctor --profile minimal
```

JSON artifact:

```bash
azure-functions-doctor doctor --format json --output doctor.json
```

Verbose fix hints:

```bash
azure-functions-doctor doctor --verbose
```

Target runtime override:

```bash
azure-functions-doctor doctor --target-python 3.12
```

## Full option reference

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--path` | string | `.` | Target project directory. |
| `--format` | enum | `table` | Output format: `table`, `json`, `sarif`, `junit`. |
| `--output` | path | unset | Write output to file instead of stdout. |
| `-v`, `--verbose` | flag | `false` | Show fix hints for non-passing checks (table mode). |
| `--debug` | flag | `false` | Enable debug logging for troubleshooting. |
| `--version` | Print the installed version and exit (no scan). |
| `--profile` | enum | `full` behavior | Rule profile: `minimal` (required gating checks), `deploy` (Azure runtime/hosting/deployment correctness), `development` (local dev-environment checks), or `full` (all rules). |
| `--rules` | path | unset | Custom rules file path. |
| `--target-python` | string | unset | Override the Azure Functions target Python runtime: `3.10`, `3.11`, `3.12`, `3.13`, `3.14` (Preview). On the Linux Consumption plan, the maximum supported version is `3.12`. |
| `--deployment-mode` | enum | `remote-build` | Deployment mode for dependency checks: `remote-build` (Azure installs from `requirements.txt`) or `local` (dependencies prebuilt/vendored locally, e.g. `.python_packages`). |

!!! note
    Supported output formats are currently `table`, `json`, `sarif`, and `junit`.

## Exit codes

- `0`: no required failures
- `1`: one or more required failures

Warnings do not change exit code unless a required failure also exists.

## Status model

Each item has one of:

- `pass`
- `warn` (optional check failed)
- `fail` (required check failed)

Section status is `fail` if any required check in the section failed.

## Output formats in detail

### Table (default)

Best for local terminal feedback.

```bash
azure-functions-doctor doctor --format table
```

Includes:

- grouped sections
- check labels and details
- summary counts
- exit code line

### JSON

Best for CI automation and post-processing.

```bash
azure-functions-doctor doctor --format json --output doctor.json
```

JSON includes:

- `metadata` (`tool_version`, `generated_at`, `target_path`, `programming_model`, `target_python`, `deployment_mode`)
- `results` (section + item diagnostics)

Contract details: [JSON Output Contract](json_output_contract.md)

### SARIF

Best for code scanning integrations.

```bash
azure-functions-doctor doctor --format sarif --output doctor.sarif
```

Generated document follows SARIF `2.1.0` structure.

### JUnit

Best for CI systems that visualize test suites.

```bash
azure-functions-doctor doctor --format junit --output doctor-junit.xml
```

Each diagnostic item is represented as a test case.

## Path targeting patterns

Single app repository:

```bash
azure-functions-doctor doctor --path .
```

Monorepo app path:

```bash
azure-functions-doctor doctor --path ./services/payments-function
```

Use explicit paths in CI to avoid accidental root-level checks.

## Profile behavior

## Target Python override

`--target-python` separates the deployed Function App runtime from the Python
interpreter running the doctor locally or in CI.

Supported values:

- `3.10`
- `3.11`
- `3.12`
- `3.13`
- `3.14`

When set, the Python version rule compares the override value instead of the
tool runtime and table output adds `Target Python: X.Y (override)` near the header.

Example:

```bash
azure-functions-doctor doctor --path ./apps/orders-function --target-python 3.12
```

When omitted, doctor keeps checking the current interpreter and labels it as the
tool runtime in the report detail.

### Default/full behavior

If `--profile` is omitted, behavior is equivalent to `full`.

`full` includes:

- required checks
- optional checks

### Minimal profile

```bash
azure-functions-doctor doctor --profile minimal
```

`minimal` includes only `required: true` rules.

Use cases:

- merge gates
- low-noise deployment blockers
- baseline compatibility checks

Reference: [Minimal Profile](minimal_profile.md)

### Deploy profile

```bash
azure-functions-doctor doctor --profile deploy
```

`deploy` runs the checks that govern **Azure runtime, hosting-plan, and
deployment correctness** — the core-group rules that determine whether the app
will start and run correctly once deployed. It excludes local
developer-environment checks and ecosystem-integration rules.

Use cases:

- pre-deploy gates that focus on cloud-runtime correctness
- CI on machines where local tooling (Core Tools, venv) is irrelevant

### Development profile

```bash
azure-functions-doctor doctor --profile development
```

`development` runs the **local developer-environment** checks: virtual
environment, Python executable, Azure Functions Core Tools, and
`local.settings.json` presence. These help onboard a workstation but are not
deployment blockers.


## Custom rules usage

Run with custom rule file:

```bash
azure-functions-doctor doctor --rules ./rules/custom.json
```

The file must:

- exist
- contain valid JSON
- satisfy `rules.schema.json`

Profiles still apply to the loaded custom rules.

Reference: [Rules](rules.md), [Custom Rules Example](examples/custom_rules.md)

## Verbose and debug modes

### Verbose mode

```bash
azure-functions-doctor doctor --verbose
```

Shows `fix:` guidance for non-passing checks in table output.

### Debug mode

```bash
azure-functions-doctor doctor --debug
```

Enables debug logging for diagnosing CLI internals and environment issues.

## Recommended command recipes

### Local fast check

```bash
azure-functions-doctor doctor --profile minimal
```

### Local full quality sweep

```bash
azure-functions-doctor doctor --profile full --verbose
```

### CI gate (required only)

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

### SARIF generation

```bash
azure-functions-doctor doctor --profile minimal --format sarif --output doctor.sarif
```

### JUnit publishing

```bash
azure-functions-doctor doctor --profile minimal --format junit --output doctor-junit.xml
```

## CI usage patterns

### Fail build automatically

Run doctor as a normal step. Exit code already captures required failures.

### Always upload artifacts

Capture exit code manually, upload report, then fail explicitly.

See full workflow in [CI Integration Example](examples/ci_integration.md).

## Programmatic API usage

Public API entry point:

```python
from azure_functions_doctor.api import run_diagnostics
```

Example:

```python
from azure_functions_doctor.api import run_diagnostics


def required_failure_count(path: str) -> int:
    count = 0
    for section in run_diagnostics(path=path, profile="minimal", rules_path=None):
        for item in section["items"]:
            if item["status"] == "fail":
                count += 1
    return count
```

Using `Doctor` directly:

```python
from pathlib import Path

from azure_functions_doctor.doctor import Doctor


def run_with_custom_rules(path: str, rules_file: str) -> list[dict]:
    doctor = Doctor(path=path, profile="full", rules_path=Path(rules_file))
    rules = doctor.load_rules()
    return doctor.run_all_checks(rules=rules)
```

Reference: [API](api.md)

## Working with other tools

### With `jq`

Count required failures in JSON:

```bash
jq '[.results[].items[] | select(.status=="fail")] | length' doctor.json
```

### With Python scripts

```python
import json
from pathlib import Path


def failing_labels(json_path: str) -> list[str]:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    labels = []
    for section in data["results"]:
        for item in section["items"]:
            if item["status"] == "fail":
                labels.append(item["label"])
    return labels
```

### With security/scanning platforms

Use SARIF format and upload `doctor.sarif` where supported.

### With test dashboards

Use JUnit format and publish `doctor-junit.xml` as a test artifact.

## Troubleshooting common usage mistakes

### Invalid path

Symptom: CLI returns parameter error.

Fix: Ensure `--path` points to an existing readable directory.

### Unknown profile

Symptom: run fails with profile validation error.

Fix: use only `minimal`, `deploy`, `development`, or `full`.

### Unsupported format

Symptom: CLI rejects `--format` value.

Fix: choose one of `table`, `json`, `sarif`, `junit`.

### Empty or invalid custom rules

Symptom: validation failure before checks run.

Fix: validate JSON and schema compatibility.

## Operational best practices

- Run `minimal` as hard CI gate
- Run `full` in local development and scheduled quality checks
- Keep JSON artifacts for failed CI runs
- Prefer explicit `--path` in monorepos
- Use `--verbose` for faster local remediation

## Related docs

- [Getting Started](getting-started.md)
- [Configuration](configuration.md)
- [Diagnostics](diagnostics.md)
- [Rules](rules.md)
- [JSON Output Contract](json_output_contract.md)
- [Troubleshooting](troubleshooting.md)
