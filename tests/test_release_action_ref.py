from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_advances_v1_action_ref() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-please.yml").read_text(encoding="utf-8")

    assert "if: steps.release.outputs.release_created == 'true'" in workflow
    assert 'git push origin "${RELEASE_SHA}:refs/heads/v1"' in workflow
