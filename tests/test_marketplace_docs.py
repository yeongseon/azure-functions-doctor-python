from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_has_marketplace_usage() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "#### GitHub Marketplace" in readme
    assert "yeongseon/azure-functions-doctor@v1" in readme
