"""E2E tests for azure-functions-doctor deployed against a real Azure Function App.

Tests that:
1. `azure-functions-doctor` passes on the deployed example project (static check).
2. The deployed function app actually responds to HTTP (proving a "doctor-clean"
   project is also a deployable project).

Usage:
    E2E_BASE_URL=https://<app>.azurewebsites.net pytest -m e2e tests/e2e -v --no-cov
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest
import requests

BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")


@pytest.fixture(scope="session", autouse=True)
def warmup() -> None:
    # Deselected by default (-m 'not e2e'), so reaching this without a URL means the
    # dedicated lane was started unconfigured: stop before any request, never skip.
    if not BASE_URL:
        pytest.exit("E2E_BASE_URL is required for the E2E lane", returncode=2)
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/HttpExample", timeout=10)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    pytest.fail("Warmup failed: /api/HttpExample did not respond within 300 s")


@pytest.mark.e2e
def test_deployed_http_trigger_responds() -> None:
    """The doctor-clean example project actually serves HTTP traffic."""
    r = requests.get(f"{BASE_URL}/api/HttpExample", params={"name": "e2e"}, timeout=30)
    assert r.status_code == 200
    assert "e2e" in r.text


@pytest.mark.e2e
def test_doctor_passes_on_example_project() -> None:
    """Running azure-functions-doctor on the example project returns exit code 0."""
    result = subprocess.run(
        [
            "azure-functions-doctor",
            "doctor",
            "--path",
            "examples/v2/http-trigger",
            "--profile",
            "minimal",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"azure-functions-doctor exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
    )
