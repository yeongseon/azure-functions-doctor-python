# Example: CI Integration

This example shows how to enforce required diagnostics in CI and publish rich artifacts.

## CI goal

- Fail builds on required issues
- Keep logs readable
- Preserve machine-readable reports for triage

Recommended command:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

Why this works:

- `minimal` keeps scope to required checks only
- `json` provides parser-safe structure
- process exit code is gate signal (`0` pass, `1` fail)

## GitHub Actions workflow

```yaml
name: Doctor Check

on:
  pull_request:
  push:
    branches: [main]

jobs:
  doctor:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install package
        run: |
          python -m pip install --upgrade pip
          python -m pip install azure-functions-doctor

      - name: Run doctor (required checks)
        run: |
          azure-functions-doctor doctor \
            --profile minimal \
            --format json \
            --output doctor.json

      - name: Upload doctor artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: doctor-report
          path: doctor.json
```

## Exit code behavior in CI

The doctor exits non-zero when required checks fail.

- Exit `0`: job continues
- Exit `1`: step fails immediately unless explicitly tolerated

If you want to always upload artifacts before failing, split gate and report steps.

## Pattern: always upload + explicit gate

```yaml
      - name: Run doctor and capture status
        id: doctor
        run: |
          set +e
          azure-functions-doctor doctor --profile minimal --format json --output doctor.json
          echo "exit_code=$?" >> "$GITHUB_OUTPUT"

      - name: Upload doctor artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: doctor-report
          path: doctor.json

      - name: Fail job when doctor failed
        if: steps.doctor.outputs.exit_code != '0'
        run: exit 1
```

## Parse JSON to produce summary

### Python parser snippet

```python
import json
from pathlib import Path


def summarize(path: str) -> tuple[int, int, int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    passed = warned = failed = 0
    for section in payload["results"]:
        for item in section["items"]:
            if item["status"] == "pass":
                passed += 1
            elif item["status"] == "warn":
                warned += 1
            elif item["status"] == "fail":
                failed += 1
    return passed, warned, failed
```

### `jq` parser snippet

```bash
fails=$(jq '[.results[].items[] | select(.status=="fail")] | length' doctor.json)
warns=$(jq '[.results[].items[] | select(.status=="warn")] | length' doctor.json)
passes=$(jq '[.results[].items[] | select(.status=="pass")] | length' doctor.json)
echo "doctor: $fails fails, $warns warnings, $passes passed"
```

## Fail only on required failures

You usually do not need custom logic because exit codes already represent required failures.

Still, explicit JSON-based checks can be useful for custom messaging:

```bash
required_failures=$(jq '[.results[].items[] | select(.status=="fail")] | length' doctor.json)
if [ "$required_failures" -gt 0 ]; then
  echo "Required diagnostics failed: $required_failures"
  exit 1
fi
```

## Multi-format publishing

For richer ecosystem integration, emit multiple formats in separate steps:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
azure-functions-doctor doctor --profile minimal --format sarif --output doctor.sarif
azure-functions-doctor doctor --profile minimal --format junit --output doctor-junit.xml
```

Then upload artifacts for each format.

## Security guidance for CI usage

- Do not execute untrusted custom rules files from forked PRs
- Keep path target explicit in monorepos (`--path`)
- Store artifacts for failed runs to speed triage

## Monorepo pattern

Run one job per function project:

```yaml
strategy:
  matrix:
    app_path:
      - apps/orders-function
      - apps/payments-function

steps:
  - run: azure-functions-doctor doctor --path ${{ matrix.app_path }} --profile minimal --format json --output doctor-${{ matrix.app_path }}.json
```

## Common CI pitfalls

- Running in wrong working directory
- Forgetting to install project dependencies before checks
- Treating warnings as failures without clear team policy
- Parsing display-only fields instead of status fields

## Azure DevOps Pipelines

Add a pipeline step to gate deployments on Azure Functions project health:

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main

pool:
  vmImage: ubuntu-latest

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: "3.12"
      addToPath: true

  - script: |
      python -m pip install --upgrade pip
      pip install azure-functions-doctor
    displayName: Install azure-functions-doctor

  - script: |
      set +e
      azure-functions-doctor doctor \
        --profile minimal \
        --format json \
        --output $(Build.ArtifactStagingDirectory)/doctor.json
      echo "##vso[task.setvariable variable=DOCTOR_EXIT_CODE]$?"
    displayName: Run azure-functions-doctor

  - task: PublishBuildArtifacts@1
    condition: always()
    inputs:
      pathToPublish: $(Build.ArtifactStagingDirectory)/doctor.json
      artifactName: doctor-report
    displayName: Publish doctor report

  - script: |
      if [ "$(DOCTOR_EXIT_CODE)" != "0" ]; then
        echo "##vso[task.logissue type=error]azure-functions-doctor found required failures"
        exit 1
      fi
    displayName: Fail pipeline on required failures
```

For SARIF output, replace `--format json` with `--format sarif --output doctor.sarif` and publish that artifact instead.

## Pre-commit hook

Run doctor as a local pre-commit check to catch issues before push:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: azure-functions-doctor
        name: Azure Functions Doctor
        language: system
        entry: azure-functions-doctor doctor --profile minimal
        pass_filenames: false
        always_run: true
```

Install and run:

```bash
pip install pre-commit azure-functions-doctor
pre-commit install
pre-commit run azure-functions-doctor
```

This runs the required-checks profile on every commit attempt. Use `--profile minimal` to keep the hook fast and focused on blocking issues only.

## VS Code task

Run doctor from the VS Code command palette via a workspace task:

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Azure Functions Doctor",
      "type": "shell",
      "command": "azure-functions-doctor doctor --profile minimal --format json --output doctor.json",
      "group": "build",
      "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "shared"
      },
      "problemMatcher": []
    }
  ]
}
```

Run it with **Terminal → Run Task → Azure Functions Doctor**. The JSON report is written to `doctor.json` in the workspace root for inspection.

## SARIF upload to GitHub Code Scanning

Upload doctor results as SARIF to surface findings in the GitHub Security tab:

### Minimal copy-paste recipe (official Action)

The fastest path is the official composite Action, which runs the doctor,
produces SARIF, and calls `github/codeql-action/upload-sarif` for you. Copy this
complete workflow into `.github/workflows/doctor-sarif.yml`:

```yaml
name: Doctor → Code Scanning

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write  # required for the SARIF upload

jobs:
  doctor:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run azure-functions-doctor (SARIF → Code Scanning)
        uses: yeongseon/azure-functions-doctor@v1
        with:
          path: .
          profile: minimal
          format: sarif
          output: doctor.sarif
          upload-sarif: "true"
```

That is the entire integration: findings appear in the repository's
**Security → Code scanning** tab on pushes and on pull requests from
branches in the same repository. The Action's
`format: sarif` + `upload-sarif: "true"` inputs map directly to the doctor CLI
and the `upload-sarif` step in [`action.yml`](https://github.com/yeongseon/azure-functions-doctor-python/blob/main/action.yml); no separate
upload step is needed.

> **Fork pull requests.** Pull requests opened from a *fork* run with a
> read-only `GITHUB_TOKEN`, so the SARIF upload step is blocked and findings
> will not appear in Code scanning for those runs. This affects only
> fork PRs; pushes and same-repository PRs upload normally.

> **Action pinning.** This copy-paste template uses mutable tags
> (`actions/checkout@v4`, `yeongseon/azure-functions-doctor@v1`) for readability.
> For a hardened, immutable setup, pin each `uses:` to a full commit SHA (with a
> `# vX` comment) so the referenced actions cannot change under you.

If you would rather wire the raw CLI yourself (e.g. to customize the run), use the
step-level fragment below instead.


```yaml
      - name: Run doctor (SARIF output)
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
        uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: doctor.sarif
          category: azure-functions-doctor

      - name: Fail job on required failures
        if: steps.doctor.outputs.exit_code != '0'
        run: exit 1
```

The SARIF report includes:

- `ruleId` mapped to the canonical rule identifier (e.g. `check_host_json_exists`)
- `level` set to `error` for required failures, `warning` for optional checks
- `locations` pointing to the project root
- `properties.hint` with the actionable fix suggestion
- `driver.rules` array listing all rules with description and category

Requires `security-events: write` permission on the job:

```yaml
jobs:
  doctor:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      contents: read
```

## Related docs

- [Configuration](../configuration.md)
- [JSON Output Contract](../json_output_contract.md)
- [Minimal Profile](../minimal_profile.md)
- [Troubleshooting](../troubleshooting.md)
