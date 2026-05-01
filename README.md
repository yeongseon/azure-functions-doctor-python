# Azure Functions Doctor

> Part of the [Azure Functions Python Cookbook](https://github.com/yeongseon/azure-functions-cookbook-python) — a collection of small tools for improving Azure Functions Python developer experience.

[![PyPI](https://img.shields.io/pypi/v/azure-functions-doctor.svg)](https://pypi.org/project/azure-functions-doctor/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-doctor/)
[![CI](https://github.com/yeongseon/azure-functions-doctor/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-doctor/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-doctor/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-doctor/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-doctor/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-doctor/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-doctor/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-doctor)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://yeongseon.github.io/azure-functions-doctor-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read this in: [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

**Azure Functions Doctor** is the pre-deploy health gate for **Azure Functions Python v2** projects — a diagnostic CLI that catches configuration issues, missing dependencies, and environment problems before they cause runtime failures in production.

---

Part of the **Azure Functions Python Cookbook**
→ Bring FastAPI-like developer experience to Azure Functions

## Why this exists

Deploying a broken Azure Functions app is expensive — the worker starts, the host reads config, and only then does it surface the issue in a production log. Common problems that slip through:

- **Missing dependencies** — `azure-functions` not in `requirements.txt`, discovered only at cold start
- **Invalid configuration** — `host.json` misconfigured, `extensionBundle` missing or outdated
- **Runtime incompatibilities** — Python version mismatch with Azure Functions runtime
- **Silent failures** — no virtual environment, Core Tools not installed, Application Insights key missing

`azure-functions-doctor` moves that failure left — catch it locally or in CI, not in production.

## What it does

- **14+ diagnostic checks** — Python version, dependencies, host.json, Core Tools, Durable Functions, and more
- **Multiple output formats** — table, JSON, SARIF, JUnit for CI integration
- **Profile support** — `minimal` or `full` rulesets depending on your needs
- **Official GitHub Action** — `yeongseon/azure-functions-doctor@v1` for CI gates

## Scope

This repository targets the decorator-based Azure Functions Python v2 programming model only.
Non-v2 repositories are detected up front and reported as unsupported instead of running v2-only checks.

- Supported model: `func.FunctionApp()` with decorators such as `@app.route()`
- Unsupported model: legacy `function.json`-based Python v1 projects

Use `azure-functions-doctor` as part of a pre-deployment checklist alongside [azure-functions-logging](https://github.com/yeongseon/azure-functions-logging-python) for observability.

## What this package does not do

This package does not own:

- **Fixing issues** — it diagnoses configuration problems but does not auto-fix them
- **API documentation** — use [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi-python) for API documentation and spec generation
- **Request validation** — use [`azure-functions-validation`](https://github.com/yeongseon/azure-functions-validation-python) for request/response validation and serialization

## Installation

From PyPI:

```bash
pip install azure-functions-doctor
```

From source:

```bash
git clone https://github.com/yeongseon/azure-functions-doctor.git
cd azure-functions-doctor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

Run the doctor in the current project:

```bash
azure-functions doctor
```

Run against a specific project:

```bash
azure-functions doctor --path ./examples/v2/http-trigger
```

Use a required-only profile:

```bash
azure-functions doctor --profile minimal
```

Output JSON for CI:

```bash
azure-functions doctor --format json
```

Pin the Azure Functions target runtime explicitly:

```bash
azure-functions doctor --target-python 3.12
```

Use `--target-python` when the Python running `azure-functions-doctor`
is not the same as the Python version your Function App will run on Azure.

### Sample output (excerpt)

```bash
azure-functions-doctor doctor --path ./examples/v2/http-trigger
```

```text
Azure Functions Doctor
Path: ./examples/v2/http-trigger

Programming Model
[✓] Programming model v2: Keyword '@app.|@bp.' found in source code (AST)

Python Env
[✓] Python version: Python 3.10.12 (tool runtime, >=3.10)
[✓] requirements.txt: requirements.txt exists
[✓] azure-functions package: Package 'azure-functions' declared in requirements.txt

Project Structure
[✓] host.json: host.json exists
[✓] host.json version: host.json version is "2.0"

Tooling
[✓] Azure Functions Core Tools (func): func detected

...

Doctor summary:
  0 fails, 5 warnings, 15 passed
Exit code: 0
```

The same command runs in CI pipelines — see [CI Integration](#ci-integration) below and [docs/deployment.md](docs/deployment.md) for details.

## CI Integration

Use `azure-functions-doctor` as a CI gate to block deployments on required failures.

### GitHub Actions (CLI)

```yaml
- name: Run azure-functions-doctor
  run: |
    pip install azure-functions-doctor
    azure-functions doctor --profile minimal --format json --output doctor.json

- name: Upload report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: doctor-report
    path: doctor.json
```

### Official GitHub Action

```yaml
- uses: yeongseon/azure-functions-doctor@v1
  with:
    path: .
    profile: minimal
    format: sarif
    output: doctor.sarif
    upload-sarif: "true"
```

See [docs/examples/ci_integration.md](docs/examples/ci_integration.md) for Azure DevOps, pre-commit, VS Code, and SARIF upload examples.

## Demo

The demo below is generated from [`demo/doctor-demo.tape`](demo/doctor-demo.tape) with VHS.
It runs the real `azure-functions doctor` CLI against the representative example
and then against an intentionally broken copy to show the pass/fail contrast.

![Doctor demo](docs/assets/doctor-demo.gif)

The final terminal state is also captured as a static image for quick inspection.

![Doctor final output](docs/assets/doctor-demo-final.png)

## Features

The default ruleset includes checks for:

- Azure Functions Python v2 decorator usage
- Python version
- virtual environment activation
- Python executable availability
- `requirements.txt`
- `azure-functions` dependency declaration
- `host.json`
- `local.settings.json` (optional)
- Azure Functions Core Tools presence and version (optional)
- Durable Functions host configuration (optional)
- Application Insights configuration (optional)
- `extensionBundle` configuration (optional)
- ASGI/WSGI callable exposure (optional)
- common unwanted files in the project tree (optional)

## Examples

- [examples/v2/http-trigger/README.md](examples/v2/http-trigger/README.md)
- [examples/v2/multi-trigger/README.md](examples/v2/multi-trigger/README.md)

## Requirements

- Python 3.10+
- Hatch for development workflows
- Azure Functions Core Tools v4+ recommended for local runs

## When to use

- Before deploying an Azure Functions app (local pre-flight check)
- In CI/CD pipelines as a deployment gate
- When onboarding a new developer to catch environment setup issues
- After upgrading Python version or Azure Functions runtime
- As a pre-commit hook for configuration validation

## Documentation

- [docs/index.md](docs/index.md)
- [docs/usage.md](docs/usage.md)
- [docs/rules.md](docs/rules.md)
- [docs/diagnostics.md](docs/diagnostics.md)
- [docs/development.md](docs/development.md)
- [docs/examples/ci_integration.md](docs/examples/ci_integration.md)

## Ecosystem

This package is part of the **Azure Functions Python Cookbook**.

**Design principle:** `azure-functions-doctor` owns pre-deploy diagnostics. It does not fix issues or generate code — it surfaces actionable findings so developers can fix them. Runtime behavior belongs to [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi-python) (API documentation and spec generation), [`azure-functions-validation`](https://github.com/yeongseon/azure-functions-validation-python) (request/response validation), and [`azure-functions-langgraph`](https://github.com/yeongseon/azure-functions-langgraph-python) (LangGraph runtime exposure).

| Package | Role |
|---------|------|
| [azure-functions-openapi](https://github.com/yeongseon/azure-functions-openapi-python) | OpenAPI spec generation and Swagger UI |
| [azure-functions-validation](https://github.com/yeongseon/azure-functions-validation-python) | Request/response validation and serialization |
| [azure-functions-db](https://github.com/yeongseon/azure-functions-db-python) | Database bindings for SQL, PostgreSQL, MySQL, SQLite, and Cosmos DB |
| [azure-functions-langgraph](https://github.com/yeongseon/azure-functions-langgraph-python) | LangGraph deployment adapter for Azure Functions |
| [azure-functions-scaffold](https://github.com/yeongseon/azure-functions-scaffold-python) | Project scaffolding CLI |
| [azure-functions-logging](https://github.com/yeongseon/azure-functions-logging-python) | Structured logging and observability |
| **azure-functions-doctor** | Pre-deploy diagnostic CLI |
| [azure-functions-durable-graph](https://github.com/yeongseon/azure-functions-durable-graph-python) | Manifest-first graph runtime with Durable Functions *(experimental)* |
| [azure-functions-python-cookbook](https://github.com/yeongseon/azure-functions-cookbook-python) | Recipes and examples |

## For AI Coding Assistants

This repository includes `llms.txt` and `llms-full.txt` for LLM-friendly documentation:

- **`llms.txt`** — Concise index of package info, CLI commands, quick start, and ecosystem overview
- **`llms-full.txt`** — Comprehensive API reference with output formats, diagnostic rules, custom rules, and CI integration patterns

When working with this codebase, LLM assistants should:

1. **Use `llms.txt` for quick reference** — package version (0.16.2), Python requirements (>=3.10,<3.15), CLI entry points
2. **Refer to `llms-full.txt` for implementation details** — output contracts, rule structure, custom rule patterns, handler types
3. **Check `src/azure_functions_doctor/cli.py`** — authoritative source for CLI options and validation
4. **Review `src/azure_functions_doctor/assets/rules/v2.json`** — complete ruleset with check definitions
5. **Consult `src/azure_functions_doctor/handlers.py`** — diagnostic rule handlers and pattern matchers

For bug reports, feature requests, or documentation improvements, please open an issue or pull request on GitHub.

## Disclaimer

This project is an independent community project and is not affiliated with,
endorsed by, or maintained by Microsoft.

Azure and Azure Functions are trademarks of Microsoft Corporation.

## License

MIT
