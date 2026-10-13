# Unbounded and Native Requirements Findings

This runnable v2 app intentionally declares `numpy` with a lower bound but no
upper bound. The declaration demonstrates both reproducibility and native-wheel
risk findings.

```bash
azure-functions-doctor doctor --path examples/v2/warn-unbound-requirements --format sarif --output doctor.sarif
```

Captured from the real CLI:

```text
check_native_dependency_risk: numpy
check_unpinned_requirements: requirements.txt:2
Exit code: 0
```
