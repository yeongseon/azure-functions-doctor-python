# Scaffold Integration Guide

`azure-functions-doctor` is designed to run immediately after scaffolding a new Azure Functions Python project.
This guide explains where doctor fits in the development lifecycle and how to integrate it with common scaffolding tools and CI pipelines.

---

## Role clarification

Doctor is a static preflight checker, not a scaffold tool.
The two tools are complementary and target different problems.

| Concern | Scaffold tool | `azure-functions-doctor` |
| --- | --- | --- |
| Create project files | ✅ | ❌ |
| Verify project files are correct | ❌ | ✅ |
| Install dependencies | ✅ | ❌ |
| Check dependency declarations | ❌ | ✅ |
| Generate bindings | ✅ | ❌ |
| Validate host configuration | ❌ | ✅ |
| Register Azure resources | ✅ | ❌ |
| Inspect runtime diagnostics | ❌ | ✅ |

The intended handoff: scaffold creates the project skeleton, doctor confirms it is structurally sound before the first `func host start` or deployment.

---

## Recommended workflow

```
scaffold new project
      │
      ▼
azure-functions-doctor doctor --profile minimal
      │
      ├── all pass → ready for development
      │
      └── any fail → fix before proceeding
```

### Step-by-step

**1. Scaffold with Azure Functions Core Tools:**

```bash
func init my-function-app --python
cd my-function-app
func new --name HttpTrigger --template "HTTP trigger"
```

**2. Run doctor immediately:**

```bash
azure-functions-doctor doctor --profile minimal
```

A freshly scaffolded project should pass all six required checks:

| Check | What it confirms |
| --- | --- |
| Python version | Target app runtime is 3.10 or newer |
| `requirements.txt` | Dependency file exists |
| `azure-functions` package | SDK is declared |
| `host.json` | Host config file exists |
| `host.json` version | `"version": "2.0"` is set |
| Orchestrator determinism | No nondeterministic calls in orchestrator/entity functions |

**3. Fix any failures before proceeding:**

```bash
# Example: missing azure-functions in requirements.txt
echo "azure-functions" >> requirements.txt
azure-functions-doctor doctor --profile minimal
```

**4. Optionally run full diagnostics for local guidance:**

```bash
azure-functions-doctor doctor --verbose
```

This surfaces optional warnings (virtual environment, Core Tools version, extension bundle, etc.) without blocking on them.

---

## GitHub Actions — scaffold and verify

Add a preflight check job to your PR workflow to catch regressions on every commit:

```yaml
name: Preflight

on:
  pull_request:
  push:
    branches: [main]

jobs:
  preflight:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install azure-functions-doctor
        run: pip install azure-functions-doctor

      - name: Run preflight check
        run: |
          azure-functions-doctor doctor \
            --profile minimal \
            --format json \
            --output doctor.json

      - name: Upload preflight report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: doctor-report
          path: doctor.json
```

Exit code `1` fails the step automatically when any required check fails.
The artifact upload uses `if: always()` to preserve the report even on failure.

---

## JSON output

Use `--format json` to produce a machine-readable report for downstream processing.

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

The output structure:

```json
{
  "status": "pass",
  "results": [
    {
      "section": "python_env",
      "status": "pass",
      "items": [
        {
          "label": "Python version",
          "status": "pass",
          "message": "Python 3.12.0"
        }
      ]
    }
  ]
}
```

Parse failures in shell:

```bash
fails=$(jq '[.results[].items[] | select(.status=="fail")] | length' doctor.json)
echo "Required failures: $fails"
```

Parse in Python:

```python
import json
from pathlib import Path

payload = json.loads(Path("doctor.json").read_text(encoding="utf-8"))
failures = [
    item
    for section in payload["results"]
    for item in section["items"]
    if item["status"] == "fail"
]
for f in failures:
    print(f"FAIL: {f['label']} — {f.get('message', '')}")
```

---

## SARIF output — GitHub Code Scanning

Surface doctor findings in the GitHub Security tab by emitting SARIF and uploading via `codeql-action`:

```yaml
      - name: Run doctor (SARIF)
        id: doctor
        run: |
          set +e
          azure-functions-doctor doctor \
            --profile minimal \
            --format sarif \
            --output doctor.sarif
          echo "exit_code=$?" >> "$GITHUB_OUTPUT"

      - name: Upload SARIF to GitHub Code Scanning
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: doctor.sarif
          category: azure-functions-doctor

      - name: Fail job on required failures
        if: steps.doctor.outputs.exit_code != '0'
        run: exit 1
```

Required job permission:

```yaml
jobs:
  preflight:
    permissions:
      security-events: write
      contents: read
```

The SARIF report maps:

- `level: error` → required check failure
- `level: warning` → optional check warning
- `ruleId` → canonical rule identifier (e.g. `check_host_json`)
- `properties.hint` → actionable fix suggestion

---

## JUnit output — test report ecosystems

Use `--format junit` to emit a JUnit XML report compatible with GitHub Actions test summaries, Azure DevOps test results, and Jenkins.

```bash
azure-functions-doctor doctor --profile minimal --format junit --output doctor-junit.xml
```

GitHub Actions test summary:

```yaml
      - name: Run doctor (JUnit)
        run: |
          azure-functions-doctor doctor \
            --profile minimal \
            --format junit \
            --output doctor-junit.xml

      - name: Publish test results
        if: always()
        uses: EnricoMi/publish-unit-test-result-action@v2
        with:
          files: doctor-junit.xml
```

---

## Multi-format pipeline

Emit all formats in a single pipeline run for maximum ecosystem coverage:

```bash
azure-functions-doctor doctor --profile minimal --format json   --output doctor.json
azure-functions-doctor doctor --profile minimal --format sarif  --output doctor.sarif
azure-functions-doctor doctor --profile minimal --format junit  --output doctor-junit.xml
```

The exit code of the first command drives pass/fail.
All three artifact uploads use `if: always()`.

---

## Monorepo pattern

Run one doctor check per function app using a matrix strategy:

```yaml
strategy:
  matrix:
    app_path:
      - apps/orders-function
      - apps/payments-function
      - apps/notifications-function

steps:
  - name: Run doctor
    run: |
      azure-functions-doctor doctor \
        --path ${{ matrix.app_path }} \
        --profile minimal \
        --format json \
        --output doctor-${{ matrix.app_path }}.json
```

Each app is checked independently. A failure in one matrix leg fails that leg only.

---

## What doctor does not replace

Doctor is intentionally narrow. Do not expect it to cover:

| Concern | Appropriate tool |
| --- | --- |
| Generate project boilerplate | `func init`, Yeoman, cookiecutter |
| OpenAPI/schema validation | `azure-functions-openapi` |
| Structured logging setup | `azure-functions-logging` |
| Input/output validation | `azure-functions-validation` |
| Azure resource provisioning | Bicep, Terraform, Azure CLI |
| Runtime diagnostics | Application Insights, Azure Monitor |
| Dependency vulnerability scanning | `pip-audit`, Dependabot |

Doctor's contract: verify that the project structure and declarations are correct before any of the above tools run.

---

## Related docs

- [Minimal Profile](minimal_profile.md)
- [Diagnostics Reference](diagnostics.md)
- [Rule Inventory](rule_inventory.md)
- [CI Integration Example](examples/ci_integration.md)
- [JSON Output Contract](json_output_contract.md)
- [RULE_POLICY](RULE_POLICY.md)
