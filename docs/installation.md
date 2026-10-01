# Installation

This page covers supported environments and installation methods for `azure-functions-doctor`.

## Requirements

- Python `>=3.10,<3.15`
- `pip` (or another PEP 517/518 compatible installer)
- Network access to PyPI for standard installation

!!! note
    Azure Functions Doctor validates Azure Functions **Python v2** projects.
    It does not target legacy Python v1 (`function.json`-driven) app layouts.

## Install from PyPI

```bash
python -m pip install azure-functions-doctor
```

The package installs these equivalent entry points:

- `azure-functions`
- `azure-functions-doctor`
- `fdoctor`

All three run the same CLI (`azure_functions_doctor.cli:cli`).

## Upgrade to latest version

```bash
python -m pip install --upgrade azure-functions-doctor
```

## Install from source

Use source install when you want to test local changes or contribute.

```bash
git clone https://github.com/yeongseon/azure-functions-doctor.git
cd azure-functions-doctor
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Install development extras:

```bash
python -m pip install -e ".[dev]"
```

Install documentation extras:

```bash
python -m pip install -e ".[docs]"
```

Install both:

```bash
python -m pip install -e ".[dev,docs]"
```

## Verify installation

Run help:

```bash
azure-functions --help
```

Run a first diagnostic in current directory:

```bash
azure-functions-doctor doctor
```

If the command is available, installation succeeded. If checks fail, that means the tool is running correctly and found project issues.

## Recommended local setup

For predictable behavior, run inside a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install azure-functions-doctor
```

## Optional system dependencies

Azure Functions Doctor itself does not require Azure Functions Core Tools, but some optional checks validate local tooling and may warn if `func` is missing.

Recommended for local development workflows:

- Azure Functions Core Tools v4+
- A shell profile where your Python venv and `func` are both on `PATH`

## Installation troubleshooting

### Command not found

If `azure-functions` is not found after install:

1. Confirm you installed into the active interpreter:

```bash
python -m pip show azure-functions-doctor
```

2. Check whether your script directory is on `PATH`.
3. Use module fallback temporarily:

```bash
python -m azure_functions_doctor.cli doctor
```

### Wrong Python version

If installation fails with Python version errors, switch to Python 3.10+ and reinstall.

### Permission denied

Use a virtual environment instead of system-level `pip` installs.

## Next steps

- Continue with [Quickstart](getting-started.md)
- Review [CLI Usage](usage.md)
- See [Troubleshooting](troubleshooting.md) for environment-specific issues
