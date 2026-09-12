# Broken Fixture: Missing azure-functions package

This fixture is intentionally broken by including `requirements.txt` without `azure-functions`.

## Expected rule failure

- `check_azure_functions_library`

## Expected doctor output

When running `azure-functions-doctor doctor --path examples/v2/broken-missing-azure-functions`, the report should include a failed `azure-functions package` check because `azure-functions` is not declared in `requirements.txt`.
