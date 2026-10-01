# Testing

## Overview
Azure Functions Doctor uses pytest as its primary testing framework. The suite spans 20+ test modules covering the CLI, diagnostic handlers, rule registration, configuration management, and error handling.

## Running Tests
You can execute the tests using the provided Makefile or by calling pytest directly.

```bash
make test                                  # Run all tests
make cov                                   # Run with coverage (terminal, HTML, and XML reports)
python -m pytest tests/test_handler.py -v  # Run a specific test file
```

## Test Structure
The codebase follows a modular test structure to ensure specific components are isolated and verified correctly.

| File | Description |
|------|-------------|
| test_handler_registry.py | Handler dispatch and per-type handler behavior |
| test_handler_registry_extended.py | Extended handler-registry coverage and edge cases |
| test_handler.py | Individual check handler implementations |
| test_toolkit_rule_checks.py | DX Toolkit rule handlers (decorator order, endpoint metadata, OpenAPI, LangGraph, durable, metadata version) |
| test_bugfix_issues.py | Regression tests for previously fixed issues |
| test_cli.py | CLI command behavior, flags, and exit codes |
| test_decorator_diagnostics.py | Decorator-order and related diagnostics |
| test_programming_model_detection.py | v1 vs v2 programming-model detection |
| test_error_handling.py | Error handling and edge cases |
| test_doctor.py | Core diagnostic engine (Doctor runner) |
| test_pyproject_dependency_manifest.py | pyproject.toml dependency-manifest handling |
| test_blueprint_registration.py | Blueprint registration detection |
| test_logging_config.py | Logging configuration |
| test_examples.py | Example project smoke tests |
| test_rule_loading.py | Rule JSON loading and validation |
| test_condition_params.py | Condition parameter parsing |
| test_native_dependency_risk.py | Native dependency risk detection |
| test_release_workflow_pins.py | Release workflow SHA-pin verification |
| test_target_resolver.py | Version resolution utilities |
| test_rules_schema.py | Rules schema consistency |
| test_api.py | Public API surface (`run_diagnostics`) |
| test_public_api.py | Public API and version exports |
| test_utils.py | Utility function tests |

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
CLI tests use Typer's CliRunner to invoke commands and verify output. They ensure the `doctor` subcommand behaves correctly with different flags such as `--format json`, `--profile minimal`, and `--path`. Exit codes are verified to be 0 for successful checks and 1 when failures occur.

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
2. Place CLI tests in `test_cli.py` using `CliRunner`.
3. Use descriptive test names following the pattern: `test_<handler>_returns_<status>_when_<condition>`.
4. Ensure all result statuses (pass, warn, fail, skip) are covered.
5. Mock external dependencies like the filesystem, executables, or network calls.
6. If adding new diagnostic rules, include corresponding handler tests.

## CI Test Matrix
The test suite runs automatically on GitHub Actions with the following configuration:
- **OS**: ubuntu-latest
- **Python Versions**: 3.10, 3.11, 3.12, 3.13, 3.14
- **Workflow**: .github/workflows/ci-test.yml

## Real Azure E2E Tests

The project includes a real Azure end-to-end test workflow that deploys an actual Function App to Azure and validates HTTP endpoints.

### Workflow

- **File**: `.github/workflows/e2e-azure.yml`
- **Trigger**: Manual (`workflow_dispatch`) or weekly schedule (Mondays 02:00 UTC)
- **Infrastructure**: Azure Consumption plan, `koreacentral` region
- **Cleanup**: Resource group deleted immediately after tests (`if: always()`)

### Running E2E Tests

```bash
gh workflow run e2e-azure.yml --ref main
```

### Required Secrets & Variables

| Name | Type | Description |
| --- | --- | --- |
| `AZURE_CLIENT_ID` | Secret | App Registration Client ID (OIDC) |
| `AZURE_TENANT_ID` | Secret | Azure Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Secret | Azure Subscription ID |
| `AZURE_LOCATION` | Variable | Azure region (default: `koreacentral`) |

### Test Report

HTML test report is uploaded as a GitHub Actions artifact (retained 30 days).
