# Dependency manifest: pyproject.toml only

Dependencies are declared only in `pyproject.toml`; there is no `requirements.txt`.
The result depends on `--deployment-mode`:

- `remote-build` (default): Azure installs from `requirements.txt`, so
  `check_requirements_txt` and `check_azure_functions_library` fail (exit `1`).
- `local`, `local-prebuilt`, or `container`: dependencies are resolved before or
  outside the Azure remote build, so both checks pass (exit `0`).

```bash
azure-functions-doctor doctor --path examples/v2/pyproject-only-dependencies --profile minimal
azure-functions-doctor doctor --path examples/v2/pyproject-only-dependencies --profile minimal --deployment-mode local
```

This is a static diagnosis of where dependencies are declared. It does not build or
deploy anything and is not Azure certification. See
[Deployment mode comparison](../../../docs/configuration.md#deployment-mode-comparison).
