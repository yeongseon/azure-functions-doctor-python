# Getting Started

This guide walks through your first successful run with `azure-functions-doctor`, explains the output model, and shows common fixes.

## 1) Prerequisites

Before running diagnostics, confirm:

- Python `>=3.10,<3.15`
- A local Azure Functions project (Python v2 decorators)
- `azure-functions-doctor` installed

If not installed yet, see [Installation](installation.md).

## 2) Project shape expected by the doctor

Azure Functions Doctor validates v2-style projects and expects signals such as:

- Decorator-based app code (for example `@app.route(...)`)
- `host.json` in project root
- `requirements.txt` in project root
- `azure-functions` listed in dependencies

!!! tip
    The tool can run on incomplete projects. Failing checks are the normal way it tells you what to fix.

## 3) First run

Run from your project root:

```bash
azure-functions-doctor doctor
```

Run against a specific path:

```bash
azure-functions-doctor doctor --path ./my-function-app
```

Use verbose mode to show fix hints:

```bash
azure-functions-doctor doctor --verbose
```

## 4) Understand output statuses

Item-level statuses:

- `pass`: check condition met
- `warn`: optional check failed
- `fail`: required check failed

Section-level status:

- Section is `fail` when any required check in that section fails
- Optional failures do not fail a section

Exit code semantics:

- Exit `0`: no required failures
- Exit `1`: one or more required failures

This makes CI gating straightforward.

## 5) Example output walkthrough

Representative output shape:

```text
Azure Functions Doctor
Path: /workspace/my-function-app

Python Env
[✓] Python version: Python 3.12.2 (>=3.10)
[✗] requirements.txt: /workspace/my-function-app/requirements.txt not found (fail)
[✗] azure-functions package: Package 'azure-functions' not declared in requirements.txt (fail)

Doctor summary (to see all details, run azure-functions-doctor doctor -v):
  2 fails, 1 warning, 5 passed
Exit code: 1
```

How to read this quickly:

1. Start at the summary line (`fails`, `warnings`, `passed`)
2. Fix all `fail` items first (required blockers)
3. Decide whether to address `warn` items now or later

## 6) Fix common failures

### Missing `requirements.txt`

Create the file:

```bash
touch requirements.txt
```

### Missing `azure-functions` declaration

Add dependency declaration:

```text
azure-functions
```

### Missing `host.json`

Create a minimal host config:

```json
{
  "version": "2.0"
}
```

### No active virtual environment

Create and activate one:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Programming model v2 check fails

Make sure your app uses decorator-based v2 style:

```python
import azure.functions as func

app = func.FunctionApp()


@app.route(route="hello")
def hello(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("ok")
```

## 7) Use profiles intentionally

Run all built-in checks (default behavior):

```bash
azure-functions-doctor doctor
```

Run only required checks:

```bash
azure-functions-doctor doctor --profile minimal
```

Use `minimal` for strict pass/fail gating and low-noise CI.

See [Minimal Profile](minimal_profile.md) for exact rule coverage.

## 8) Machine-readable formats

JSON:

```bash
azure-functions-doctor doctor --format json --output doctor-report.json
```

SARIF:

```bash
azure-functions-doctor doctor --format sarif --output doctor.sarif
```

JUnit:

```bash
azure-functions-doctor doctor --format junit --output doctor-junit.xml
```

!!! note
    The current CLI supports `table`, `json`, `sarif`, and `junit` output formats.

## 9) Programmatic usage (Python)

Use the public API for custom tooling:

```python
from azure_functions_doctor.api import run_diagnostics


def count_required_failures(path: str) -> int:
    failures = 0
    for section in run_diagnostics(path=path, profile="full", rules_path=None):
        for item in section["items"]:
            if item["status"] == "fail":
                failures += 1
    return failures
```

See [API Reference](api.md) for detailed module docs.

## 10) Suggested first-week workflow

For teams adopting the doctor:

1. Run `azure-functions-doctor doctor` locally during development
2. Fix all required failures before PR creation
3. Add CI gate using `--profile minimal --format json`
4. Publish JSON/SARIF/JUnit artifacts for visibility
5. Periodically run full profile to capture optional quality signals

## 11) Where to go next

- [CLI Usage](usage.md) for complete flag reference
- [Rules](rules.md) for per-rule behavior and remediation
- [Diagnostics](diagnostics.md) for status mapping details
- [JSON Output Contract](json_output_contract.md) for parser-safe fields
- [Troubleshooting](troubleshooting.md) for operational issues
