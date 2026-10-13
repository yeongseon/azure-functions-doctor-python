# Unresolved Binding Connection Finding

This runnable v2 app intentionally references `MyStorage` from a queue trigger
without defining a matching app setting.

```bash
azure-functions-doctor doctor --path examples/v2/broken-unresolved-connection --format sarif --output doctor.sarif
```

Captured from the real CLI:

```text
check_binding_connection_resolution: function_app.py:6
Exit code: 0
```
