from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_advances_v1_action_ref() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-please.yml").read_text(encoding="utf-8")
    release_ref_steps = workflow.split(
        "      - name: Check out the released Action commit\n", maxsplit=1
    )[1].split("      # README.md", maxsplit=1)[0]

    assert release_ref_steps.count("if: steps.release.outputs.release_created == 'true'") == 2
    assert "token: ${{ secrets.RELEASE_PLEASE_TOKEN }}" in release_ref_steps
    assert "ref: ${{ steps.release.outputs.sha }}" in release_ref_steps
    assert 'git push origin "${RELEASE_SHA}:refs/heads/v1"' in release_ref_steps
