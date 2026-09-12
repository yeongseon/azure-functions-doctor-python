# Multi-Trigger Example

Demonstrates three trigger types in a single Azure Functions Python v2 app:

| Trigger | Route / Schedule | Description |
| --- | --- | --- |
| HTTP | `GET/POST /api/hello` | Returns a JSON greeting |
| Timer | `0 */5 * * * *` | Heartbeat every 5 minutes |
| Queue | `tasks` queue | Processes JSON messages from Azure Storage Queue |

## Project Structure

```
multi-trigger/
├── function_app.py          # HTTP + Timer + Queue triggers
├── host.json               # extensionBundle v4
├── requirements.txt
├── local.settings.sample.json  # copy to local.settings.json before running
├── .funcignore
└── .gitignore
```

## Run Locally

```bash
cd examples/v2/multi-trigger
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.sample.json local.settings.json
func start
```

## Diagnose

```bash
azure-functions-doctor doctor --path examples/v2/multi-trigger
```

All checks should pass for this example.
