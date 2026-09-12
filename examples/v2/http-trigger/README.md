# HTTP Trigger Example

Minimal single HTTP trigger for the Azure Functions Python v2 programming model.

## Project Structure

```
http-trigger/
├── function_app.py          # HTTP trigger (@app.route)
├── host.json               # extensionBundle v4
├── requirements.txt
├── local.settings.sample.json  # copy to local.settings.json before running
├── .funcignore
└── .gitignore
```

## Run Locally

```bash
cd examples/v2/http-trigger
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.sample.json local.settings.json
func start
```

Test the endpoint:

```bash
curl "http://localhost:7071/api/HttpExample?name=World"
```

## Diagnose

```bash
azure-functions-doctor doctor --path examples/v2/http-trigger
```

All checks should pass for this example.
