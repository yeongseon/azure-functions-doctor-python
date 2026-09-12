# Timer Trigger Example

Minimal Azure Functions Python v2 timer trigger that fires every 5 minutes.

## Project Structure

```
timer-trigger/
├── function_app.py          # Timer trigger (@app.timer_trigger)
├── host.json               # extensionBundle v4
├── requirements.txt
├── local.settings.sample.json  # copy to local.settings.json before running
├── .funcignore
└── .gitignore
```

## Run Locally

```bash
cd examples/v2/timer-trigger
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.sample.json local.settings.json
func start
```

## Diagnose

```bash
azure-functions-doctor doctor --path examples/v2/timer-trigger
```

All checks should pass for this example.
