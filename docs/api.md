# API Reference

The public entry point for programmatic usage is
`azure_functions_doctor.api.run_diagnostics(path, profile, rules_path, target_python)`.
It uses the same diagnostics engine as `azure-functions-doctor doctor`, then returns
structured results that can be consumed in scripts, CI pipelines, or custom tooling.

## Public API at a Glance

| API | Purpose | Typical usage |
| --- | --- | --- |
| `run_diagnostics(path, profile, rules_path, target_python)` | Run all checks and return section-level results. | CI validation, custom wrappers, pre-commit hooks. |
| `Doctor(path, profile, rules_path, target_python)` | Lower-level runner with explicit lifecycle methods. | Advanced control over rule loading and execution. |
| `CheckResult` | Result object for one check item. | Output processing and custom reporting. |
| `SectionResult` | Result object for a group of checks. | Rendering grouped summaries by category. |
| `HandlerRegistry` | Maps rule `type` to execution handlers. | Handler extension and internal diagnostics flow. |

## Programmatic Usage with `run_diagnostics`

Use `run_diagnostics` when you want behavior that matches the CLI while staying
inside Python code.

```python
from pathlib import Path

from azure_functions_doctor.api import run_diagnostics


def summarize_failures(project_path: str) -> int:
    results = run_diagnostics(path=project_path, profile="full", rules_path=None)
    failed_required = 0

    for section in results:
        for item in section["items"]:
            if item["status"] == "fail":
                failed_required += 1

    return failed_required


if __name__ == "__main__":
    target = str(Path(".").resolve())
    failed = summarize_failures(target)
    raise SystemExit(1 if failed else 0)
```

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `path` | `str` | Yes | File system path to the Azure Functions app root. |
| `profile` | `str \| None` | No | Rule profile: `"minimal"` (required checks only), `"deploy"` (runtime/hosting/deployment correctness), `"development"` (dev-environment checks), or `"full"` (default behavior: all rules). |
| `rules_path` | `pathlib.Path | None` | No | Optional path to a custom rules file matching the rules schema. |
| `target_python` | `str | None` | No | Override target Python runtime version (e.g. `"3.12"`). Defaults to `None` (use tool runtime). |

### Return Value

`run_diagnostics` returns `list[SectionResult]`, where each section includes:

- `title`: human-readable section title
- `category`: machine-friendly section key
- `status`: `pass` or `fail` at section level
- `items`: list of `CheckResult` entries

## Working with `CheckResult` and `SectionResult`

The following snippet shows safe access to optional fields (`hint`, `hint_url`)
while creating a report.

```python
from azure_functions_doctor.api import run_diagnostics


def flatten_results(path: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for section in run_diagnostics(path=path, profile=None, rules_path=None):
        for item in section["items"]:
            rows.append(
                {
                    "section": section["category"],
                    "label": item["label"],
                    "status": item["status"],
                    "value": item["value"],
                    "hint": item.get("hint", ""),
                    "hint_url": item.get("hint_url", ""),
                }
            )
    return rows
```

## Using `Doctor` Directly

Use `Doctor` if you need to separate rule loading, validation, and execution.

```python
from pathlib import Path

from azure_functions_doctor.doctor import Doctor


def run_with_custom_rules(project_dir: str, custom_rules_file: str) -> list[dict]:
    doctor = Doctor(
        path=project_dir,
        profile="minimal",
        rules_path=Path(custom_rules_file),
    )
    rules = doctor.load_rules()
    return doctor.run_all_checks(rules=rules)
```

## Handler Registry Integration

`HandlerRegistry` stores the mapping from rule `type` to concrete handler methods.
Most users do not need to call it directly, but it is useful in internal extensions.

```python
from pathlib import Path

from azure_functions_doctor.handlers import HandlerRegistry


def run_single_rule(rule: dict, project_path: str) -> dict[str, str]:
    registry = HandlerRegistry()
    result = registry.handle(rule=rule, path=Path(project_path))
    return result
```

## CLI

::: azure_functions_doctor.cli

## Doctor

::: azure_functions_doctor.doctor

## Handlers

::: azure_functions_doctor.handlers

## Target Resolver

::: azure_functions_doctor.target_resolver

## Utility

::: azure_functions_doctor.utils
