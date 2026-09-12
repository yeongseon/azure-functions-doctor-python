# Deploy to Azure

This guide walks you through deploying an Azure Functions Python app with a diagnostics-first workflow.
You will run `azure-functions-doctor` first, confirm the project is healthy, then provision Azure resources and publish.

## Who this guide is for

You write Python and use `pip`, but Azure is new to you.
This guide is for first-time Azure users who want copy-paste commands and clear checkpoints.

## What you are deploying

`azure-functions-doctor` is a CLI diagnostics tool, not a runtime framework.
It checks Azure Functions project health before deployment so you catch problems early.

In this guide you will:

- Run doctor on a healthy sample project (`examples/v2/http-trigger`)
- Compare that with a broken sample (`examples/v2/broken-missing-host-json`)
- Generate text, JSON, SARIF, and JUnit outputs for local and CI use
- Deploy only after checks pass

## Azure concepts you need for this guide

> New to Azure plans? Read [Choose an Azure Functions Hosting Plan](choose-a-plan.md).

| Term | What it means |
|---|---|
| **Function App** | Your deployed Azure Functions application (like a cloud-hosted Python app). |
| **Hosting plan** | Compute model that controls scaling, cold starts, timeout, and cost. |
| **Resource Group** | A container for related Azure resources; delete it to clean up everything. |
| **Storage Account** | Required backing resource for Azure Functions state and operations. |

## Recommended plan for this repo

| | |
|---|---|
| **Default plan** | Flex Consumption |
| **Why** | Lowest friction for first deployment, scale-to-zero, and enough timeout for typical Python HTTP samples. |
| **Switch to Premium if** | You need faster cold starts, always-warm instances, or very large dependency footprints. |

## Before you start

| Requirement | How to check | Install if missing |
|---|---|---|
| Azure account | [portal.azure.com](https://portal.azure.com) | [Create free account](https://azure.microsoft.com/free/) |
| Azure CLI | `az --version` | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| Azure Functions Core Tools v4 | `func --version` | [Install Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local#install-the-azure-functions-core-tools) |
| Python 3.10-3.14 | `python3 --version` | [python.org](https://www.python.org/downloads/) |
| Doctor CLI v0.20.0 | `pip show azure-functions-doctor` | `python3 -m pip install azure-functions-doctor` |

Install doctor if needed:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install azure-functions-doctor
```

## Read these warnings before provisioning

1. Storage account names must be globally unique (lowercase letters and numbers only, 3–24 characters).
2. Keep all resources in the same Azure region to avoid avoidable latency and provisioning issues.
3. Local settings do not auto-sync to Azure; use app settings after deployment when needed.
4. First publish can take a few minutes because Azure performs a remote build for Python dependencies.
5. Deleting local files does not delete Azure resources; remove the resource group to stop billing.
6. Doctor validates your function project, not your Azure subscription state; permission, quota, policy, and region availability issues can still fail deployment.

## Run doctor before you deploy

This is the core workflow for this repository: diagnose first, deploy second.

Healthy project check:

```bash
azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal
```

Representative text output:

```text
Azure Functions Doctor
Path: /data/GitHub/azure-functions-doctor/examples/v2/http-trigger

Python Env
[PASS] Python version: Python 3.11.11
[PASS] requirements.txt: found
[PASS] azure-functions package: declared in requirements.txt

Project Structure
[PASS] host.json: found
[PASS] host.json version: "2.0"

Durable
[PASS] Orchestrator determinism: No nondeterministic calls detected in orchestrators

Doctor summary (to see all details, run azure-functions-doctor doctor -v):
  0 fails, 0 warnings, 6 passed
Exit code: 0
```

Broken project detection (missing `host.json`):

```bash
azure-functions-doctor doctor --path examples/v2/broken-missing-host-json --profile minimal
```

Representative text output:

```text
Azure Functions Doctor
Path: /data/GitHub/azure-functions-doctor/examples/v2/broken-missing-host-json

Python Env
[PASS] Python version: Python 3.11.11
[PASS] requirements.txt: found
[PASS] azure-functions package: declared in requirements.txt

Project Structure
[FAIL] host.json: file not found (fail)
[FAIL] host.json version: host.json missing or invalid (fail)

Durable
[PASS] Orchestrator determinism: No nondeterministic calls detected in orchestrators

Doctor summary (to see all details, run azure-functions-doctor doctor -v):
  2 fails, 0 warnings, 4 passed
Exit code: 1
```

Machine-readable output formats:

```bash
# JSON
azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal --format json --output doctor-report.json

# SARIF (for code scanning / security tooling)
azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal --format sarif --output doctor-report.sarif

# JUnit (for CI test dashboards)
azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal --format junit --output doctor-report.xml

# Summary JSON sidecar (quick pass/fail counts)
azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal --summary-json doctor-summary.json
```

Representative JSON output (`doctor-report.json`):

```json
{
  "metadata": {
    "tool_version": "0.20.0",
    "target_path": "/data/GitHub/azure-functions-doctor/examples/v2/http-trigger",
    "programming_model": "v2",
    "target_python": null
  },
  "results": [
    {
      "title": "Python Env",
      "status": "pass",
      "items": [
        {
          "label": "Python version",
          "status": "pass"
        }
      ]
    }
  ]
}
```

Representative SARIF output (`doctor-report.sarif`):

```json
{
  "version": "2.1.0",
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "azure-functions-doctor",
          "version": "0.20.0"
        }
      },
      "results": []
    }
  ]
}
```

Representative JUnit output (`doctor-report.xml`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<testsuite name="func-doctor" tests="6" failures="0" skipped="0" time="0.021">
  <testcase classname="Python Env" name="Python version" />
  <testcase classname="Project Structure" name="host.json" />
</testsuite>
```

Representative summary sidecar content:

```json
{"passed":6,"warned":0,"failed":0}
```

When checks fail, doctor exits with code `1`. Use that exit code to block deployment.

## Deploy the healthy example

This section deploys `examples/v2/http-trigger` on Flex Consumption.

### Step 1 — Set deployment variables

```bash
SUBSCRIPTION_ID="00000000-0000-0000-0000-000000000000"
RESOURCE_GROUP="rg-doctor-http"
LOCATION="koreacentral"
STORAGE_ACCOUNT="stdoctorhttp$(date +%s | tail -c 6)"
FUNCTIONAPP_NAME="func-doctor-http"
```

### Step 2 — Sign in and select subscription

```bash
az login
az account set --subscription "$SUBSCRIPTION_ID"
```

### Step 3 — Confirm Flex region support

```bash
az functionapp list-flexconsumption-locations -o table
```

### Step 4 — Re-run doctor on the healthy sample (deployment gate)

```bash
azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal
```

Proceed only if the command exits with `0`.

### Step 5 — Create resource group

```bash
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
```

### Step 6 — Create storage account

```bash
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS
```

### Step 7 — Create Function App (Flex Consumption)

```bash
az functionapp create \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-account "$STORAGE_ACCOUNT" \
  --flexconsumption-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11
```

### Step 8 — Publish the healthy example

```bash
func azure functionapp publish "$FUNCTIONAPP_NAME" --python --source examples/v2/http-trigger
```

If your Core Tools version does not support `--source`, run this equivalent command instead:

```bash
(cd examples/v2/http-trigger && func azure functionapp publish "$FUNCTIONAPP_NAME" --python)
```

### Step 9 — Verify the deployed endpoint

```bash
BASE_URL="https://$FUNCTIONAPP_NAME.azurewebsites.net"
curl -i "$BASE_URL/api/HttpExample?name=Azure"
curl -i "$BASE_URL/api/HttpExample"
```

Expected behavior: both calls return HTTP `200` with plain-text responses.

## Use doctor in CI

Run diagnostics before publish, and fail the pipeline when doctor finds required check failures.

Example GitHub Actions workflow:

```yaml
name: deploy-with-doctor

on:
  push:
    branches: [main]

jobs:
  verify-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install tooling
        run: |
          python -m pip install --upgrade pip
          pip install azure-functions-doctor

      - name: Run doctor (text)
        run: azure-functions-doctor doctor --profile minimal

      - name: Run doctor (JSON)
        run: azure-functions-doctor doctor --profile minimal --format json --output doctor-report.json

      - name: Run doctor (SARIF)
        run: azure-functions-doctor doctor --profile minimal --format sarif --output doctor-report.sarif

      - name: Run doctor (JUnit)
        run: azure-functions-doctor doctor --profile minimal --format junit --output doctor-report.xml

      - name: Run doctor (summary sidecar)
        run: azure-functions-doctor doctor --profile minimal --summary-json doctor-summary.json

      - name: Publish
        if: success()
        run: func azure functionapp publish "$FUNCTIONAPP_NAME" --python
```

## If you need a different plan

This guide uses Flex Consumption by default. If you need Premium or Dedicated, keep the same diagnostics workflow and replace only the Function App provisioning commands.

See [Choose an Azure Functions Hosting Plan](choose-a-plan.md) for plan-by-plan command blocks.

## Troubleshooting

### Doctor says pass, but deployment fails

| Symptom | Usually means | How to fix |
|---|---|---|
| `AuthorizationFailed` or `SubscriptionNotFound` | Subscription/permissions issue | Confirm account and subscription: `az account show`, then `az account set --subscription "$SUBSCRIPTION_ID"` |
| `StorageAccountAlreadyTaken` | Storage account name collision | Generate a new globally unique value for `$STORAGE_ACCOUNT` |
| `LocationNotAvailableForResourceType` | Flex unavailable in that region | Check available regions: `az functionapp list-flexconsumption-locations -o table` |
| Publish fails with remote build errors | Azure-side build issue or missing dependency metadata | Verify `requirements.txt`, retry publish, then inspect deployment logs |

Doctor validates project structure and configuration; it does not validate Azure account state, RBAC, quota, policies, or regional service availability.

### Doctor says fail, but project works locally

| Symptom | Usually means | How to fix |
|---|---|---|
| Missing `host.json` or invalid schema warning | Local run path is different from deployment path | Run doctor against the exact folder being deployed |
| Dependency check failures | Local environment has packages installed globally/venv, but project metadata is incomplete | Pin required packages in `requirements.txt` and rerun doctor |
| Fails on one machine, passes in CI | Environment drift | Use `--profile minimal`, compare versions, and keep Python/CLI versions aligned |

Useful verification commands:

```bash
python3 --version
az --version
func --version
pip show azure-functions-doctor
azure-functions-doctor doctor --profile minimal -v
```

### Before opening an issue

If you're stuck, please include the following when opening a GitHub issue:

```bash
# 1. Azure CLI version
az --version

# 2. Functions Core Tools version
func --version

# 3. Python version
python --version

# 4. Doctor version
pip show azure-functions-doctor

# 5. Doctor output on your project
azure-functions-doctor doctor -v

# 6. Function App status (if deployed)
az functionapp show \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "{state:state, runtime:siteConfig.linuxFxVersion}"

# 7. Recent logs (if deployed)
func azure functionapp logstream "$FUNCTIONAPP_NAME"
```



---

## Clean up resources

Delete the resource group to remove all related Azure resources and stop billing.

```bash
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
```

Confirm cleanup:

```bash
az group show --name "$RESOURCE_GROUP"
```

If deletion has completed, the command returns a not-found error.

## Sources

- [Azure Functions Python quickstart](https://learn.microsoft.com/azure/azure-functions/create-first-function-cli-python)
- [Azure Functions Core Tools reference](https://learn.microsoft.com/azure/azure-functions/functions-core-tools-reference)
- [Azure Functions hosting plans](https://learn.microsoft.com/azure/azure-functions/functions-scale)
- [Flex Consumption plan](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
- [SARIF v2.1.0 specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
- [JUnit XML format reference](https://llg.cubic.org/docs/junit/)

## See Also

- [Choose an Azure Functions Hosting Plan](choose-a-plan.md) — Plan selection guide with decision tree
- [README](https://github.com/yeongseon/azure-functions-doctor/blob/main/README.md)
- [Examples: healthy HTTP trigger](https://github.com/yeongseon/azure-functions-doctor/tree/main/examples/v2/http-trigger)
- [Examples: broken missing host.json](https://github.com/yeongseon/azure-functions-doctor/tree/main/examples/v2/broken-missing-host-json)
- [`azure-functions-scaffold`](https://github.com/yeongseon/azure-functions-scaffold)
- [`azure-functions-validation`](https://github.com/yeongseon/azure-functions-validation)
- [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi)
- [`azure-functions-logging`](https://github.com/yeongseon/azure-functions-logging)
- [`azure-functions-langgraph`](https://github.com/yeongseon/azure-functions-langgraph)
