from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_action_has_marketplace_metadata() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")

    assert re.search(r"^name: Azure Functions Doctor$", action, re.MULTILINE)
    description = re.search(r"^description: (?P<value>.+)$", action, re.MULTILINE)
    assert description is not None
    assert 1 <= len(description.group("value")) <= 125
    assert re.search(r"^branding:\n  icon: activity\n  color: blue$", action, re.MULTILINE)
