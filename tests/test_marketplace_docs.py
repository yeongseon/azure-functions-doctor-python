from __future__ import annotations

import importlib.util
from pathlib import Path
import re
from types import ModuleType

from azure_functions_doctor import __version__

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_docs_version.py"


def _load_sync_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_docs_version", SYNC_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_has_marketplace_usage() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    marketplace = readme.split("#### GitHub Marketplace\n", maxsplit=1)[1].split(
        "```yaml", maxsplit=1
    )[0]

    assert "yeongseon/azure-functions-doctor@v1" in marketplace
    assert f"yeongseon/azure-functions-doctor@v{__version__}" in marketplace


def test_readme_immutable_action_ref_is_version_synced() -> None:
    substitutions = _load_sync_module()._substitutions("9.8.7")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for pattern, replacement in substitutions["README.md"]:
        readme = re.sub(pattern, replacement, readme)

    assert "yeongseon/azure-functions-doctor@v9.8.7" in readme
