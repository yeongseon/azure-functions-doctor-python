"""Developer prerequisites (not the product doctor) and allowlisted cleanup."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys


def doctor(live: bool = False) -> int:
    healthy = sys.version_info >= (3, 11)
    print("Developer environment prerequisites (make doctor; not product diagnostics)")
    print(f"python REQUIRED >=3.11: {sys.version.split()[0]} ({sys.executable})")
    for module in ("venv", "ruff", "mypy", "pytest", "bandit"):
        found = importlib.util.find_spec(module) is not None
        print(f"{module} REQUIRED: {'found' if found else 'MISSING'}")
        healthy = healthy and found
    hatch = shutil.which("hatch")
    environment = sys.prefix != sys.base_prefix
    print(f"hatch or active venv REQUIRED: {hatch or ('venv' if environment else 'MISSING')}")
    healthy = healthy and (hatch is not None or environment)
    for tool in ("ruff", "mypy", "pytest", "bandit"):
        path = shutil.which(tool)
        print(f"{tool} executable REQUIRED on PATH: {path or 'MISSING'}")
        healthy = healthy and path is not None
    for tool in ("func", "azurite"):
        path = shutil.which(tool)
        print(f"{tool} REQUIRED only for host-smoke/integration/verify: {path or 'MISSING'}")
        if live:
            healthy = healthy and path is not None
    for tool in ("az", "docker", "pre-commit"):
        print(f"{tool} OPTIONAL: {shutil.which(tool) or 'not installed'}")
    return 0 if healthy else 1


def clean(root: Path) -> None:
    for name in (
        "test-results",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        "coverage.xml",
        "htmlcov",
        "site",
        "__pycache__",
    ):
        path = root / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    for path in root.glob("*.egg-info"):
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    for tree in ("src", "tests", "tools", "scripts", "examples"):
        for path in (root / tree).rglob("__pycache__"):
            if not any(part in {".venv", "venv", "env"} for part in path.parts):
                if path.is_symlink():
                    path.unlink()
                else:
                    shutil.rmtree(path)
