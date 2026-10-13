# Unsupported Linux Runtime Finding

This runnable v2 app intentionally declares `Python|3.9` in its Bicep
infrastructure template.

```bash
azure-functions-doctor doctor --path examples/v2/broken-linux-fx-version --format sarif --output doctor.sarif
```

Captured from the real CLI:

```text
check_linux_fx_version: main.bicep — linuxFxVersion Python|3.9 is unsupported
Exit code: 0
```
