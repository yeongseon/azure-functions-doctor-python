# Blueprint Example

Demonstrates the `func.Blueprint()` pattern for modular Azure Functions Python v2 apps.
The HTTP trigger is defined in `http_blueprint.py` and registered into the main app via `app.register_functions(bp)`.

## Project Structure

```
blueprint/
├── function_app.py          # FunctionApp() + register_functions(bp)
├── http_blueprint.py       # Blueprint with @bp.route()
├── host.json               # extensionBundle v4
├── requirements.txt
├── local.settings.sample.json  # copy to local.settings.json before running
├── .funcignore
└── .gitignore
```

## Run Locally

```bash
cd examples/v2/blueprint
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.sample.json local.settings.json
func start
```

## Diagnose

```bash
azure-functions-doctor doctor --path examples/v2/blueprint
```

All checks should pass for this example.
