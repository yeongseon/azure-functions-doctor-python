# Nondeterministic Orchestrator Finding

This runnable Durable Functions v2 app intentionally calls `random.randint`
inside an orchestrator, which cannot replay deterministically.

```bash
azure-functions-doctor doctor --path examples/v2/warn-nondeterministic-orchestrator --format sarif --output doctor.sarif
```

Captured from the real CLI:

```text
check_durable_nondeterminism: function_app.py:11
Exit code: 1
```
