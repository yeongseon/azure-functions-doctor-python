# Monorepo example

Two independent local Azure Functions apps live side by side under `services/`:

| App | Path | Shape |
| --- | --- | --- |
| API | `services/api` | `host.json` intentionally missing, so required checks fail (exit `1`). |
| Worker | `services/worker` | Complete app; `requirements.txt` declares the native-risk package `pyodbc`, so only the worker reports it. |

`services/api` also anchors the SARIF repo-root rebasing contract: scanning
`--path services/api` must prefix every artifactLocation URI with `services/api/`
(issue #392). Its `host.json` is missing on purpose so both SARIF branches (located file
and scan-root fallback) are exercised.

## Target one app at a time

Doctor diagnoses exactly the directory you pass with `--path`. It does **not**
discover apps in a monorepo for you and does not change its default scanning scope; run
it once per app (from this directory):

```bash
cd examples/monorepo
azure-functions-doctor doctor --path services/api --profile deploy
azure-functions-doctor doctor --path services/worker --profile deploy
```

Expected, deterministic differences between the two reports:

- `services/api`: exits `1`; `check_host_json` and `check_host_json_version` fail; nothing
  from `services/worker` appears.
- `services/worker`: exits `0`; `check_native_dependency_risk` warns about `pyodbc`; nothing
  from `services/api` appears.

Pointing `--path` at the monorepo root (`--path .`) is **not** equivalent to scanning both
apps: file-based checks such as `host.json` and `requirements.txt` look at the root
directory itself, so they fail there even though each app is fine on its own.

Add `--format json --output <file>` (or `sarif`) with a different output file per app to
compare reports. In CI, use one job (or matrix entry) per app path.
