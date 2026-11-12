# Testing

## Overview
Azure Functions Doctor uses pytest as its primary testing framework. The suite spans more than 80 `tests/test_*.py` modules (85 at the time of writing) covering the CLI, diagnostic handlers, rule loading, programming-model detection, output contracts, inspection hardening, release/CI tooling and documentation guards.

## Running Tests
You can execute the tests using the provided Makefile or by calling pytest directly.

```bash
make test                                  # Run all tests
make cov                                   # Run with coverage (terminal, HTML, and XML reports)
python -m pytest tests/test_handler.py -v  # Run a specific test file
```

## Test Structure
Tests live flat under `tests/`. The table lists **representative** modules by area; it is
**non-exhaustive**, so list `tests/` (or run `python -m pytest --collect-only -q`) for the full set.

| Area | Representative modules | What they cover |
|------|------------------------|-----------------|
| Handlers and rule dispatch | `test_handler.py`, `test_handler_registry.py`, `test_handler_registry_extended.py`, `test_toolkit_rule_checks.py`, `test_condition_params.py` | Individual rule-type handlers and `HandlerRegistry` dispatch, including DX Toolkit heuristics |
| Rule files | `test_rule_loading.py`, `test_rules_schema.py`, `test_profiles.py` | Built-in `v2.json` loading, `rules.schema.json` validity, profile selection |
| Programming-model detection | `test_programming_model_detection.py`, `test_model_rule_consistency.py` | v1 / v2 / mixed / unknown classification and agreement between the preflight gate and the `Programming model v2` rule |
| Rule behavior on projects | `test_blueprint_registration.py`, `test_decorator_diagnostics.py`, `test_native_dependency_risk.py`, `test_flex_*.py`, `test_runtime_*.py`, `test_python_runtime_lifecycle.py`, `test_catalog_verdict_matrix.py` | Per-rule positive/negative behavior on filesystem projects |
| CLI and output contract | `test_cli.py`, `test_gate_severity_independence.py`, `test_output_contract_schema.py`, `test_finding_contract_v2.py`, `test_skip_status.py`, `test_api.py`, `test_public_api.py` | Flags, exit codes, JSON / SARIF / JUnit / table output, `skip` status, public API |
| Inspection hardening | `test_inspection_*.py`, `test_requirements_*.py`, `test_inventory_*.py`, `test_security_*.py`, `test_traversal_governance.py` | Bounded, deterministic reading of project files and security evidence |
| Examples | `test_examples.py` | The bundled `examples/v2/*` projects (healthy and `broken-*`) |
| Regression guards | `test_bugfix_issues.py`, `test_scan_characterization.py`, `test_error_handling.py` | Previously fixed defects and scan isolation |
| Release, CI and docs tooling | `test_release_workflow_pins.py`, `test_workflow_pin_hygiene.py`, `test_ci_classify_changes.py`, `test_release_notes.py`, `test_docs_consistency.py` | Workflow pin hygiene, change classification, release-note rendering, documentation drift guards |
| Opt-in E2E selector | `test_e2e_selector_contract.py`, `tests/e2e/test_doctor_e2e.py` | The `e2e` marker selects exactly the two live E2E tests; the tests themselves need `E2E_BASE_URL` |

## Fixture Families

Choose the fixture by what the test must prove. All paths below exist in the repository.

| Family | Location | Use it for |
|--------|----------|------------|
| Programming-model projects | `tests/fixtures/v1/`, `tests/fixtures/mixed/`, `tests/fixtures/unknown/` | Detection results and the non-v2 early-exit message. `v1` has a `function.json` function, `mixed` combines `function_app.py` with a legacy function, `unknown` contains only `.gitkeep` (no signals) |
| Per-rule v2 projects | `tests/fixtures/v2/<case>/` (e.g. `decorator_order_correct`, `decorator_order_inverted`, `blueprint_registered`, `blueprint_unregistered`, `endpoint_metadata_covered`, `endpoint_metadata_missing`, `native_deps_present`, `pure_python_only`) | A positive and a negative project for one rule. The list is representative, not exhaustive |
| Bundled example projects | `examples/v2/` (healthy: `http-trigger`, `timer-trigger`, `multi-trigger`, `blueprint`; defective: `broken-*`, `warn-*`) | End-to-end rule checks on realistic apps. `test_examples.py` requires each `broken-*` example to fail on the one rule it was designed for; the examples are also documentation, so keep them readable |
| Recorded output baselines | `tests/fixtures/inspection-compatibility/*.json`, `native-main.json`, `requirements-main.b64` | Exact table / JSON / SARIF output compared by `test_inspection_compatibility.py` and the native-legacy tests |
| Inline `tmp_path` projects | created inside the test | Small, self-describing cases (one file or one edge case); preferred when a fixture directory would be used by a single test |
| Real-host smoke app | `tests/host_smoke/` | Not a unit fixture. It is the app the `host-smoke` CI job starts under a real Functions host |

## Test Patterns

### Handler Tests (test_handler.py)
These tests verify individual diagnostic check handlers. They use the `tmp_path` fixture to create isolated filesystem environments. Testing covers various outcomes including pass, warn, fail, and skip.

Specific handlers tested include:
- file_exists and path_exists
- package_declared
- source_code_contains
- executable_exists
- compare_version
- conditional_exists
- callable_detection

### CLI Tests (test_cli.py)
CLI tests use `CliRunner` from `typer.testing` to invoke commands and verify output. They ensure the `doctor` subcommand behaves correctly with different flags such as `--format json`, `--profile minimal`, and `--path`. Exit codes are verified to be 0 for successful checks and 1 when failures occur.

### Rules Tests
- **test_rule_loading.py**: Validates the loading of the built-in `v2.json` ruleset (and custom rule files).
- **test_rules_schema.py**: Ensures rule JSON files adhere to the defined schema.
- Custom rules: Verifies that the `--rules` flag correctly loads external rule files.

### Error Handling (test_error_handling.py)
These tests confirm that the system handles failures gracefully. They check handler failures, exception recovery, and context logging to ensure the application doesn't crash during unexpected diagnostic errors.

### Example Smoke Tests (test_examples.py)
Lightweight smoke tests validate that the projects in the `examples/` directory remain runnable. This provides a baseline level of end-to-end verification without the overhead of full infrastructure tests.

## Coverage Configuration
Coverage settings are defined in `pyproject.toml`.
- **Source**: src/azure_functions_doctor
- **Branch coverage**: Enabled
- **Reports**: Terminal (missing lines), HTML, and XML
- **pytest options**: `--cov=src/azure_functions_doctor --cov-report=xml --cov-report=term-missing -ra -q -m 'not e2e'`

## Writing New Tests
When contributing new features or bug fixes, follow these guidelines:

1. Place handler tests in `test_handler.py` using the `tmp_path` fixture.
2. Place CLI tests in `test_cli.py` using `CliRunner` from `typer.testing`.
3. Use descriptive test names following the pattern: `test_<handler>_returns_<status>_when_<condition>`.
4. Ensure all result statuses (pass, warn, fail, skip) are covered.
5. Mock external dependencies like the filesystem, executables, or network calls.
6. If adding new diagnostic rules, include corresponding handler tests.

## Adding a Test for a New Rule

Use this checklist together with the rule steps in [Development](development.md#adding-a-new-rule):

1. **Positive and negative project.** Provide one project where the rule passes and one where it does
   not. Reuse an existing `tests/fixtures/v2/<case>/` pair or a `tmp_path` project; add a new
   `tests/fixtures/v2/<case>/` directory only when several tests share it. Add an `examples/v2/broken-*`
   project only when it also serves users as documentation (and extend `test_examples.py`).
2. **Deterministic finding contract.** Assert the rule's `label`, `status` (`pass` / `warn` / `fail` /
   `skip`) and, where relevant, `rule_id` and the user-facing hint. The same project must always
   produce the same result; do not depend on the machine's installed packages, network, the clock or
   the CI environment (see how `test_examples.py` excludes environment-dependent labels).
3. **False-positive control.** Add at least one near-miss project that must **not** trigger the rule
   (for example the `blueprint_unrelated_registration` and unimported-lookalike cases), in line with
   [Rule Policy](RULE_POLICY.md).
4. **Right lane.** Rule findings belong in the offline unit tests above. Do not put them in `tests/e2e/`
   or `tests/host_smoke/`: those lanes only prove deployment and host behavior (next section).
5. **Keep drift guards green.** If a built-in rule is added or removed, regenerate
   `docs/rule_inventory.md` with `python scripts/gen_rule_inventory.py` and run
   `python scripts/check_docs_consistency.py`; `test_docs_consistency.py` also checks the README rule
   count against `v2.json`.
6. **Coverage.** The coverage floor is 95% (`fail_under = 95` in `pyproject.toml`).

## CI Test Matrix
The test suite runs automatically on GitHub Actions with the following configuration:
- **OS**: ubuntu-latest
- **Python Versions**: 3.11, 3.12, 3.13, 3.14
- **Workflow**: .github/workflows/ci-test.yml

## What Each Lane Proves

| Lane | Where it runs | A pass proves |
| --- | --- | --- |
| Offline tests | `make test`; the `test` and `minimum-dependencies` jobs in `ci-test.yml` | The source behaves as specified on each supported Python and at the minimum declared dependency versions, with the 95% coverage floor. No Azure, Functions host or deployed app is involved. |
| Real host smoke | `host-smoke` in `ci-test.yml` (Python 3.11, 3.12) | The doctor passes on a minimal app, and that app starts under a real Functions host (Core Tools v4 and Azurite) and answers an HTTP request. Local emulation, not Azure. |
| Installed-wheel CLI | the `artifact-*` jobs in `ci-test.yml`; `doctor-runtime-gate` in `publish-pypi.yml` | The built wheel installs on Python 3.11 (3.10 rejects it) and its `azure-functions-doctor` CLI runs on the example app from outside the checkout. |
| Release-chain Azure E2E | `azure-e2e` in `publish-pypi.yml`, which runs `e2e-azure.yml`, for every release tag | The release commit's example app, which the doctor passes, deploys to a real Azure Function App and serves HTTP. |

### What each lane does not prove

- **Offline tests** do not prove that an app starts on a Functions host or works on Azure; a rule finding
  is a static, offline judgment about project files and configuration.
- **Real host smoke** covers only the single `tests/host_smoke/` app on local emulation (Core Tools and
  Azurite); it does not exercise individual diagnostic rules or Azure.
- **Installed-wheel CLI** proves packaging and the CLI entry point on one example app, not rule coverage.
- **Release-chain Azure E2E** proves the release commit's example app deploys and serves HTTP on one Linux
  Consumption app; it does not validate every rule or other hosting plans. The two tests in
  `tests/e2e/test_doctor_e2e.py` are marked `e2e` and deselected from the default suite.

### Scan performance probe (opt-in)

`tools/benchmark_scan.py <project-path>` is a manual probe, not a test and not part of any CI job.
For the `minimal` and `full` profiles it prints, as JSON, the number of source reads and AST parses,
elapsed seconds and a SHA-256 digest of the ordered findings; `DOCTOR_UNCACHED=1` disables the parse
cache for comparison. Equal digests show a change did not alter findings; timings from single runs are
indicative only. See [Scan performance](scan-performance.md). It is intentionally kept, and a pass or
fail of the suite says nothing about scan speed.

A local run is not Azure certification, including `make e2e-local` and `make e2e-azure` against an app you deployed yourself. Only `e2e-azure.yml` deploys to Azure, and the release chain runs it at every tag.

## Real Azure E2E Tests

The project includes a real Azure end-to-end test workflow that deploys an actual Function App to Azure and validates HTTP endpoints.

### Workflow

- **File**: `.github/workflows/e2e-azure.yml`
- **Trigger**: Manual (`workflow_dispatch`), and as the `azure-e2e` release-certification gate that `publish-pypi.yml` calls (`workflow_call`) for every release tag; there is no schedule
- **Infrastructure**: Linux Consumption plan (`Y1`/Dynamic) running Python 3.12, deployed by `infra/main.bicep` to the `koreacentral` region by default
- **Note**: Linux Consumption is the legacy plan (retires 30 September 2028) and is used here only because it is the cheapest throwaway target for a short certification run
- **Cleanup**: Resource group deleted immediately after tests (`if: always()`)

### Running E2E Tests

```bash
gh workflow run e2e-azure.yml --ref main
```

To run the two tests against an app that is already deployed:

```bash
E2E_BASE_URL=https://<app>.azurewebsites.net make e2e-azure
```

Both tests carry the `e2e` marker, which the default suite deselects (`-m 'not e2e'`), so the dedicated run selects them with `-m e2e` and skips the offline coverage gate (`--no-cov`). `E2E_BASE_URL` is required: when it is unset the run stops with exit code 2 and the message `E2E_BASE_URL is required for the E2E lane` before sending any request; the tests are never reported as skipped.

### Required Secrets & Variables

| Name | Type | Description |
| --- | --- | --- |
| `AZURE_CLIENT_ID` | Secret | App Registration Client ID (OIDC) |
| `AZURE_TENANT_ID` | Secret | Azure Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Secret | Azure Subscription ID |
| `AZURE_LOCATION` | Variable | Azure region (default: `koreacentral`) |

### Test Report

HTML test report is uploaded as a GitHub Actions artifact (retained 30 days).
