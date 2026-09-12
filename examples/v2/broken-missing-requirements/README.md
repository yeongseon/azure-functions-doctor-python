# Broken Fixture: Missing requirements.txt

This fixture is intentionally broken by omitting `requirements.txt`.

## Expected rule failure

- `check_requirements_txt`

## Expected doctor output

When running `azure-functions-doctor doctor --path examples/v2/broken-missing-requirements`, the report should include a failed `requirements.txt` check because no dependency file exists at the project root.
