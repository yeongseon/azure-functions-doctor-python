# Profile Comparison on One Project

The same local project can produce different results under different `--profile`
values, because each profile selects a different set of checks. This page runs all four
profiles against one checked-in, intentionally broken, synthetic example:
`examples/v2/broken-flex-runtime-config`. It declares `python 3.9` under
`functionAppConfig.runtime`, which `check_flex_runtime_config` reports as a failure.

Everything is offline and read-only: no Azure subscription, credentials, or Core Tools
calls are needed.

## Run it

```bash
azure-functions-doctor doctor --path examples/v2/broken-flex-runtime-config --profile minimal
azure-functions-doctor doctor --path examples/v2/broken-flex-runtime-config --profile deploy
azure-functions-doctor doctor --path examples/v2/broken-flex-runtime-config --profile development
azure-functions-doctor doctor --path examples/v2/broken-flex-runtime-config --profile full
```

Add `--format json` to read results by `rule_id` instead of terminal text.

## What changes

| Profile | Selected checks | `check_flex_runtime_config` | Exit code |
| --- | --- | --- | --- |
| `minimal` | 6 required rules only | not selected | `0` |
| `deploy` | core Azure runtime/hosting/deployment rules | `fail` | `1` |
| `development` | 5 local developer-environment rules | not selected | `0` |
| `full` | every rule | `fail` | `1` |

Stable subset used by `tests/test_profile_comparison.py`:

- `minimal` selects exactly `check_python_version`, `check_requirements_txt`,
  `check_azure_functions_library`, `check_host_json`, `check_host_json_version`, and
  `check_durable_nondeterminism`.
- `deploy` and `full` both select `check_flex_runtime_config`; `minimal` and `development`
  do not.
- `development` selects exactly `check_venv`, `check_python_executable`,
  `check_local_settings`, `check_func_cli`, and `check_func_core_tools_version`.

## Environment-sensitive checks

Some checks depend on your machine or checkout rather than on the project, so their
status can differ between runs and are deliberately not asserted:

- `check_venv`, `check_func_cli`, `check_func_core_tools_version`, and
  `check_python_executable` (selected by `development` and `full`) inspect your local tooling.
- `check_app_insights`, `check_funcignore`, and `check_local_settings_git_tracked`
  (selected by `deploy` and `full`) depend on local settings, files, and git state.

## Reading the result correctly

A rule that a profile does not select is **not** evidence that the project is healthy
for that concern. In the table above, `minimal` exits `0` and reports no failures even
though the declared Flex runtime is unsupported, simply because
`check_flex_runtime_config` is not selected. Likewise, a clean run is a statement about
the static files Doctor inspected, not a certification of any deployed Azure resource.
Pick the profile that matches what you intend to gate, for example `deploy` for a
pre-deployment check. See [CLI Usage](usage.md#profile-behavior) and
[Minimal Profile](minimal_profile.md).
