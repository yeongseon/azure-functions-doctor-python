# Validation Integration Findings

This runnable v2 app intentionally contains an inverted validation/logging
decorator stack and an HTTP route without `@validate_http`.

```bash
azure-functions-doctor doctor --path examples/v2/validation-integration --format sarif --output doctor.sarif
```

Captured from the real CLI:

```text
check_decorator_order: function_app.py:8
check_endpoint_metadata: function_app.py:16
Exit code: 0
```
