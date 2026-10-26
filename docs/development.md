# Development Guide

This project uses Hatch, pytest, Ruff, mypy, and Bandit. Ruff handles both
linting and formatting; Black is not used.

The development workflow is designed to keep diagnostics deterministic, rules schema-validated,
and release behavior stable across supported Python versions.

## Prerequisites

- Python 3.11+
- Hatch
- Make

## Setup

```bash
make bootstrap
source .venv/bin/activate
make install
make precommit-install
```

## Common Commands

```bash
make format
make lint
make typecheck
make test
make security
make check-all
```

## Project Areas

- `src/azure_functions_doctor/api.py`: stable programmatic API (`run_diagnostics`)
- `src/azure_functions_doctor/cli.py`: Typer-based CLI (`azure-functions-doctor doctor`)
- `src/azure_functions_doctor/doctor.py`: orchestration, rule loading, section aggregation
- `src/azure_functions_doctor/handlers/`: handler implementations (`registry.py`) and shared helpers/types (`_helpers.py`)
- `src/azure_functions_doctor/assets/rules/v2.json`: built-in diagnostics rules
- `src/azure_functions_doctor/schemas/rules.schema.json`: schema for rule validation
- `tests/`: unit tests, CLI tests, rule/schema tests, integration-style checks
- `docs/`: MkDocs content
- `examples/v2/`: representative sample apps used for smoke checks

## Architecture Overview

Execution path in normal usage:

1. CLI parses options (`--path`, `--profile`, `--rules`, `--target-python`,
   `--deployment-mode`, `--hosting-plan`, output format options).
2. CLI constructs `Doctor(path, profile=..., rules_path=..., target_python=...)`
   directly; embedders call the equivalent `run_diagnostics(...)` wrapper in
   `api.py`.
3. `Doctor` loads rules (built-in `v2.json` or custom rules file).
4. Rule schema validation runs before any handler execution.
5. `HandlerRegistry` dispatches each rule by `type`.
6. Results are canonicalized as `pass`/`warn`/`fail` and emitted.

## Testing Strategy

The project follows layered testing to keep regressions localized:

- Unit tests for handler behavior and edge conditions.
- Unit tests for rule loading and schema validation.
- CLI tests for command behavior, options, and exit codes.
- Smoke tests against sample Azure Functions v2 projects.

Recommended local sequence before opening a PR:

```bash
make format
make lint
make typecheck
make test
make security
```

### What each verification lane proves

| Lane | Entry point | Evidence and limits |
| --- | --- | --- |
| Repository prerequisites | `make doctor` | Read-only tool discovery: Hatch, Python 3.11 and git are required; `func` and `azurite` are optional local-host tools. This is not the product command `azure-functions-doctor doctor`. |
| Offline library and CLI tests | `make test` / `make check-all` | Deterministic diagnostics, CLI contracts and sample fixtures, with the 95% coverage floor. The default pytest selector excludes live E2E tests. No Azure certification is performed. |
| Real local Functions host smoke | CI `host-smoke` in `ci-test.yml` | Runs the installed Doctor against `tests/host_smoke`, boots that app with Core Tools and Azurite on Python 3.11 and 3.12, then probes HTTP. This proves local host behavior, not Azure deployment. |
| Installed-wheel compatibility | CI artifact jobs in `ci-test.yml` | Builds distribution artifacts, verifies Python 3.10 rejects the wheel, and installs it on Python 3.11 to exercise the installed CLI. This is packaging/runtime evidence, not Azure certification. |
| Live E2E tests | `make e2e-azure` (delegates to Hatch's `e2e-azure` script) | Selects both `e2e` tests with `--no-cov`; `E2E_BASE_URL` must be set or the lane stops non-zero before requests. Running locally against a supplied URL does not create a release certification record. |
| Release-chain Azure certification | `e2e-azure.yml`, called by `publish-pypi.yml` | Deploys to real Azure, runs both live E2E tests at the release ref, and uploads the `azure-cert` record. Publication depends on this gate along with the other release gates. |

`make e2e-local` runs the same live E2E selector against
`http://localhost:7071`; start an isolated local host before using it. It is
not an Azure deployment or certification command. The E2E lane deliberately
does not apply the offline coverage floor to its two tests; the offline
coverage requirement remains unchanged.

## Adding a New Rule

When adding or modifying a built-in check, keep the rule-first flow:

1. Edit `src/azure_functions_doctor/assets/rules/v2.json`.
2. Ensure the rule object satisfies `rules.schema.json`.
3. If needed, extend handler behavior in the `handlers/` package (`registry.py`).
4. Add tests for both pass and non-pass outcomes.
5. Update docs (`diagnostics.md`, `rule_inventory.md`, and this guide if needed).

### Rule Authoring Checklist

| Field | Required | Notes |
| --- | --- | --- |
| `id` | Yes | Unique and stable identifier for tests and release notes. |
| `type` | Yes | Must map to a registered handler type. |
| `label` | Yes | User-facing check name shown in output. |
| `section` | Yes | Used for grouped output and section summaries. |
| `required` | Yes | Controls `fail` vs `warn` mapping. |
| `condition` | Usually | Handler-specific contract (for example `target`, `jsonpath`, `patterns`). |
| `check_order` | Recommended | Keeps output deterministic and stable for CI snapshots. |

## Adding a New Handler

Use this process to introduce a new rule type:

1. Add the new literal to the `Rule["type"]` definition in `handlers/_helpers.py`.
2. Implement `_handle_<name>(self, rule, path, context=None)` in `handlers/registry.py`.
3. Register the type-to-method mapping in `_RULE_DISPATCH` (`handlers/_helpers.py`); `HandlerRegistry.__init__` binds it automatically.
4. Extend `rules.schema.json` so the new type is schema-valid.
5. Add tests in `tests/test_handler.py` and registry tests if needed.

### Minimal handler example

Add the method inside `HandlerRegistry` (`handlers/registry.py`), decorated with
`@_rule_handler` so it is registered in `_RULE_DISPATCH`:

```python
from pathlib import Path


class HandlerRegistry:
    # ... existing handlers ...

    @_rule_handler
    def _handle_sample(self, rule: dict, path: Path, context=None) -> dict[str, str]:
        _ = (rule, context)
        marker = path / ".doctor-marker"
        if marker.exists():
            return {"status": "pass", "detail": "Marker exists"}
        return {"status": "fail", "detail": "Marker missing"}
```

## Debugging Tips

- Use `azure-functions-doctor doctor --debug` to enable debug logging.
- Use `--profile minimal` to isolate required checks first.
- Run with `--format json` to inspect raw section/item output precisely.
- Use `--rules <path>` to reproduce issues with a minimal custom ruleset.
- Validate rule JSON structure against the schema before debugging handlers.

Programmatic debugging pattern:

```python
from pathlib import Path

from azure_functions_doctor.doctor import Doctor


def debug_run(project_path: str) -> list[dict]:
    doctor = Doctor(path=project_path, profile="full", rules_path=None)
    rules = doctor.load_rules()
    print(f"Loaded {len(rules)} rules")
    return doctor.run_all_checks(rules=rules)


if __name__ == "__main__":
    results = debug_run(str(Path(".").resolve()))
    print(f"Sections: {len(results)}")
```

## CI/CD Pipeline Explanation

CI enforces code quality and compatibility before merge:

- Formatting and lint checks verify style and static quality.
- Type checks validate annotations and API contracts.
- Test jobs run the suite across supported Python versions.
- Security checks (Bandit and dependency auditing where configured) run in CI.
- Documentation changes are expected to remain consistent with runtime behavior.

For release confidence, rule changes should include tests and documentation updates in the same PR.

## Workflow

1. Update runtime code or the v2 ruleset.
2. Add or update tests.
3. Run `make check-all`.
4. Use English for code comments, docs, and commit messages.
