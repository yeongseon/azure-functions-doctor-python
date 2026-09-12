# Azure Functions Doctor

Validate Azure Functions Python v2 projects before they fail in local runtime or CI.

`azure-functions-doctor` is a diagnostics CLI and API that checks required project health signals, reports optional operational guidance, and returns deterministic exit codes for automation.

## Why teams use it

- Catch missing baseline files (`host.json`, `requirements.txt`) early
- Verify runtime and dependency declarations before deployment
- Gate merges on required blockers while preserving optional guidance
- Export machine-readable diagnostics for CI and code-scanning systems

## Working example

Install and run in the current project:

```bash
python -m pip install azure-functions-doctor
azure-functions-doctor doctor
```

Run required-only checks in CI:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

## What it checks

Built-in diagnostics currently include:

- Python version support
- v2 decorator programming model signal
- virtual environment presence
- Python executable path validity
- `requirements.txt` and `azure-functions` declaration
- `host.json` presence
- optional tooling, telemetry, extension, and cleanup checks

Reference: [Rule Inventory](rule_inventory.md)

## Output and gating model

Item statuses:

- `pass`
- `warn` (optional check failed)
- `fail` (required check failed)

Exit code contract:

- `0` when required checks all pass
- `1` when any required check fails

This enables direct CI usage without custom gate wrappers.

## Feature highlights

- Declarative rules with schema validation
- Profile-based execution (`minimal`, `deploy`, `development`, `full`)
- Multiple output formats (`table`, `json`, `sarif`, `junit`)
- Custom rule file support via `--rules`
- Programmatic API for pipeline/tool integration

## CLI and API entry points

- CLI: `azure-functions-doctor doctor`
- API: `from azure_functions_doctor.api import run_diagnostics`

Programmatic example:

```python
from azure_functions_doctor.api import run_diagnostics


def has_required_failures(path: str) -> bool:
    for section in run_diagnostics(path=path, profile="minimal", rules_path=None):
        for item in section["items"]:
            if item["status"] == "fail":
                return True
    return False
```

## Documentation map

### Get started

- [Installation](installation.md)
- [Quickstart](getting-started.md)
- [Configuration](configuration.md)

### User guide

- [CLI Usage](usage.md)
- [Diagnostics](diagnostics.md)
- [Rules](rules.md)
- [Rule Inventory](rule_inventory.md)
- [Deploy-Risk Rule Pages](rules/check_python_runtime_lifecycle.md) — one page per runtime/deployment rule; error messages land on the rule
- [Minimal Profile](minimal_profile.md)
- [JSON Output Contract](json_output_contract.md)
- [Handlers](handlers.md)

### Examples

- [Basic Check](examples/basic_check.md)
- [CI Integration](examples/ci_integration.md)
- [Custom Rules](examples/custom_rules.md)

### Maintenance and policies

- [Supported Versions](supported_versions.md)
- [Semver Policy](semver_policy.md)
- [Comparison vs Official Skill](comparison.md)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)

## Typical adoption path

1. Install package in your development environment
2. Run `azure-functions-doctor doctor` locally and fix required failures
3. Add CI job using `--profile minimal --format json`
4. Publish JSON/SARIF/JUnit artifacts for visibility
5. Add optional custom rules for organization-specific policy

## Notes on scope

!!! note
    Azure Functions Doctor targets the Python v2 decorator model.
    Legacy Python v1 (`function.json`-oriented) projects are out of scope.

## Need help?

Start with [Troubleshooting](troubleshooting.md), then review [FAQ](faq.md). If behavior looks incorrect, include command, version, and JSON output snippet when opening an issue.
