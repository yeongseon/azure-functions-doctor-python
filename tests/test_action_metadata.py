from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_action_has_marketplace_metadata() -> None:
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert action["name"] == "Azure Functions Doctor"
    assert 1 <= len(action["description"]) <= 125
    assert action["branding"] == {"icon": "activity", "color": "blue"}
