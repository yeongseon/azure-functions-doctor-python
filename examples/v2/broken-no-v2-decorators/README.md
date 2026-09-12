# Broken Fixture: No v2 Decorators

This fixture is intentionally broken by omitting v2 decorator usage (`@app.*`).

The project has valid `host.json`, `requirements.txt`, and `azure-functions` declared,
but `function_app.py` does not use `func.FunctionApp()` or any `@app.*` decorators.

## Expected doctor failure

- `programming_model` fail-fast detection (`unknown`)

## Expected doctor output

When running `azure-functions-doctor doctor --path examples/v2/broken-no-v2-decorators`, the report
should include a failed `Python v2 programming model was not detected` result because no
`func.FunctionApp()`, `Blueprint()`, or `@app.` / `@bp.` trigger decorators are present.
