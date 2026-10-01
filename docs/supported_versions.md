# Supported Versions

## Python

Azure Functions Doctor supports **Python 3.10 and above**.

- Minimum supported version: 3.10
- Targeted versions: 3.10, 3.11, 3.12, 3.13, 3.14

### Python Compatibility Notes

- The package metadata and CI matrix are aligned to supported interpreter versions.
- New Python versions are added after CI coverage and baseline diagnostics stability checks.
- Unsupported versions may appear to run but are not considered supported behavior.

Example local verification:

```python
import sys


def is_supported_python() -> bool:
    major = sys.version_info.major
    minor = sys.version_info.minor
    return major == 3 and minor >= 10


if __name__ == "__main__":
    print(is_supported_python())
```

## Azure Functions Model

Azure Functions Doctor supports the **Azure Functions Python v2 programming model** only.

- Supported: `func.FunctionApp()` and decorator-based triggers
- Not supported: legacy `function.json`-based Python v1 projects

## Azure Functions Runtime Compatibility

Azure Functions Doctor validates project readiness for current Azure Functions host expectations,
with emphasis on local tooling and host configuration used by Python v2 apps.

| Component | Compatibility Baseline | Notes |
| --- | --- | --- |
| Azure Functions programming model | Python v2 | Requires decorator-based app style (`@app.route`, etc.). |
| Local runtime tooling | Core Tools v4+ (recommended) | Reported as optional warning when missing or older than baseline. |
| Host config file | `host.json` required | Required check for project structure validity. |
| Local settings file | `local.settings.json` optional | Warning-oriented check for local development ergonomics. |

## CI Test Matrix

The CI pipeline should continuously validate package behavior against supported versions.

| Dimension | Values |
| --- | --- |
| OS | `ubuntu-latest` |
| Python versions | `3.10`, `3.11`, `3.12`, `3.13`, `3.14` |
| Test gates | lint, typecheck, unit tests, security checks |

Representative GitHub Actions matrix shape:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest]
    python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]
```

## CLI and API Compatibility Expectations

- CLI command surface: `azure-functions-doctor doctor` with documented options.
- Public API surface: `run_diagnostics(path, profile, rules_path, target_python)`.
- Changes to public behavior should be reflected in tests, docs, and release notes.

Programmatic compatibility check example:

```python
from azure_functions_doctor.api import run_diagnostics


def smoke(path: str) -> int:
    sections = run_diagnostics(path=path, profile="minimal", rules_path=None)
    required_failures = 0
    for section in sections:
        for item in section["items"]:
            if item["status"] == "fail":
                required_failures += 1
    return required_failures
```

## Maintenance Policy

When the supported baseline changes, update:

- `pyproject.toml`
- `src/azure_functions_doctor/assets/rules/v2.json`
- CI matrices
- this document and the main README

## Deprecation Policy

Version support changes follow a predictable process to avoid surprise breakages.

1. Announce intent to deprecate a version in release notes.
2. Keep the version in CI during the deprecation notice period.
3. Update support declarations (`pyproject.toml`, docs, CI matrix) in a coordinated release.
4. Remove deprecated version from active support and close related compatibility issues.

### Deprecation Triggers

- Upstream ecosystem shifts (Python end-of-life, Azure Functions platform changes).
- Inability to keep quality gates green for a version without disproportionate maintenance cost.
- Security or packaging constraints that block safe continued support.

### Communication Requirements

- Document the change in release notes and changelog.
- Reflect the new baseline in `supported_versions.md` and README.
- Ensure tests and diagnostics rules match the new support floor.
