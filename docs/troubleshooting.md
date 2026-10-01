# Troubleshooting

Use this guide to diagnose common install, runtime, output, and CI issues with `azure-functions-doctor`.

## Quick triage checklist

Before deep debugging:

1. Confirm Python version is supported (`>=3.10,<3.15`)
2. Confirm you are in the intended project directory (`--path` if needed)
3. Re-run with `--verbose` for fix hints
4. Re-run with `--debug` for diagnostic logging context
5. Export JSON (`--format json`) for parser-friendly issue sharing

## Installation issues

### Problem: `azure-functions` command not found

Likely causes:

- package installed in a different interpreter
- script directory not on `PATH`

Actions:

```bash
python -m pip show azure-functions-doctor
```

Use module fallback if needed:

```bash
python -m azure_functions_doctor.cli doctor
```

### Problem: install fails due to Python version

The package requires Python `>=3.10,<3.15`.

Action:

- switch interpreter version
- reinstall into matching environment

### Problem: permission errors during install

Action:

- install inside a virtual environment instead of global Python

## Command and input errors

### Problem: invalid path error

The CLI validates that target path:

- exists
- is a directory
- is readable

Action:

```bash
azure-functions-doctor doctor --path ./correct/project/path
```

### Problem: unknown profile error

Only `minimal` and `full` are valid profile values.

Action:

```bash
azure-functions-doctor doctor --profile minimal
```

### Problem: invalid format error

Supported formats are:

- `table`
- `json`
- `sarif`
- `junit`

## Diagnostic result confusion

### Problem: "many passes but command failed"

Cause: at least one required item has status `fail`.

Action:

- inspect summary fail count
- run with `--verbose`
- fix required items first

### Problem: warnings appear unexpectedly

Cause: optional checks failed in full profile.

Action:

- use `--profile minimal` for required-only gating
- keep full profile for local quality insight

### Problem: v2 programming model check fails

Cause: source does not expose expected `@app.` decorator signal.

Action:

- ensure project uses decorator-based v2 style
- verify relevant files are under target path

## Project setup failures and fixes

### Missing `requirements.txt`

Create and populate dependency file.

### `azure-functions` not declared

Add `azure-functions` line to `requirements.txt`.

### Missing `host.json`

Create minimal config:

```json
{
  "version": "2.0"
}
```

### Virtual environment check fails

Activate a venv before running:

```bash
python -m venv .venv
source .venv/bin/activate
```

## Output and artifact issues

### Problem: JSON parsing fails

Common causes:

- command was run without `--format json`
- parser consumed wrong file

Action:

```bash
azure-functions-doctor doctor --format json --output doctor.json
```

Then parse `doctor.json` only.

### Problem: no output file written

Cause: output path is invalid or not writable.

Action:

- ensure parent directory is writable
- use explicit relative or absolute output path

## Custom rules issues

### Problem: custom rules path does not exist

Action:

- verify `--rules` path is correct and points to a file

### Problem: custom rules fail schema validation

Cause: missing required fields or invalid `type`/`condition` structure.

Action:

- validate JSON syntax
- align with `src/azure_functions_doctor/schemas/rules.schema.json`

### Problem: unknown check type behavior

Cause: rule `type` is not registered in handler registry.

Action:

- use supported rule types listed in [Rules](rules.md)

## CI integration issues

### Problem: build fails unexpectedly

Cause: required check failed; exit code is `1` by design.

Action:

- inspect JSON artifact
- list all failing item labels
- fix required blockers

### Problem: CI logs are hard to read

Action:

- write JSON to file (`--output doctor.json`)
- upload artifact even on failure
- optionally generate JUnit/SARIF artifacts

### Problem: monorepo checks target wrong path

Action:

- pass explicit per-app `--path`
- use matrix strategy for multiple function projects

## False positives and edge cases

Heuristic checks can behave differently in unusual repository layouts.

Recommended issue report contents:

- doctor version
- command used
- target path
- JSON output snippet
- minimal reproducible repository shape

## Helpful commands

Verbose local run:

```bash
azure-functions-doctor doctor --verbose
```

Debug run:

```bash
azure-functions-doctor doctor --debug
```

Required-only CI run:

```bash
azure-functions-doctor doctor --profile minimal --format json --output doctor.json
```

## Related docs

- [Getting Started](getting-started.md)
- [Usage](usage.md)
- [Configuration](configuration.md)
- [FAQ](faq.md)
- [JSON Output Contract](json_output_contract.md)
