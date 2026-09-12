# Broken Fixture: Missing host.json

This fixture is intentionally broken by omitting `host.json`.

## Expected rule failure

- `check_host_json`

## Expected doctor output

When running `azure-functions-doctor doctor --path examples/v2/broken-missing-host-json`, the report should include a failed `host.json` check because the file does not exist at the project root.
