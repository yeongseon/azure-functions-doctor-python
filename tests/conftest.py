import pytest


@pytest.fixture(autouse=True)
def isolate_verification_summary(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    if request.module.__name__.split(".")[-1].startswith("test_verification"):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
