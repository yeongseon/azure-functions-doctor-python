"""Bounded collection checks for the E2E test selector contract (#591).

Both ``tests/e2e/test_doctor_e2e.py`` functions carry ``@pytest.mark.e2e``.
These checks pin the selectors that depend on that marker so a
marker-only change cannot silently make any of them select zero tests
again:

- ``pytest -m e2e tests/e2e/`` (the advertised local/Azure E2E entrypoint,
  used by both Hatch's ``e2e-azure`` script and the Makefile's
  ``e2e-local``/``e2e-azure`` targets) must select exactly the two E2E
  functions.
- The ``pytest tests/e2e ...`` command that ``.github/workflows/e2e-azure.yml``
  runs for release certification must select both of them as well; selecting
  none is pytest exit 5 and fails the release gate.
- The default library-wide suite (``pyproject.toml``'s ``addopts`` applies
  ``-m 'not e2e'`` unconditionally) must select neither of them, regardless
  of whether ``E2E_BASE_URL`` is set.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
E2E_WORKFLOW = ROOT / ".github/workflows/e2e-azure.yml"
E2E_TEST_NAMES = (
    "test_deployed_http_trigger_responds",
    "test_doctor_passes_on_example_project",
)


def _collect(
    *args: str, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ | (env_overrides or {})
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args, "--collect-only", "-v", "--no-cov"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_e2e_marker_selector_collects_both_e2e_functions() -> None:
    """``pytest -m e2e tests/e2e/`` -- the command Hatch's ``e2e-azure``
    script and both Makefile E2E targets delegate to -- must select
    exactly the two live-Azure tests, not zero."""
    result = _collect("-m", "e2e", "tests/e2e/")
    assert result.returncode == 0, result.stdout + result.stderr
    for name in E2E_TEST_NAMES:
        assert name in result.stdout


def test_default_suite_excludes_e2e_tests_without_base_url() -> None:
    """The library-wide default suite must not select either E2E
    function when ``E2E_BASE_URL`` is unset (the common case: a
    contributor running ``pytest``/``make test`` locally or in CI without
    live Azure credentials)."""
    result = _collect("tests/", env_overrides={"E2E_BASE_URL": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    for name in E2E_TEST_NAMES:
        assert name not in result.stdout


def test_default_suite_excludes_e2e_tests_even_with_base_url_present() -> None:
    """The exclusion is marker-based, not just env-skip-based: even when
    ``E2E_BASE_URL`` happens to be set in the environment, the default
    suite (which always applies ``-m 'not e2e'``) must still not select
    either E2E function."""
    result = _collect("tests/", env_overrides={"E2E_BASE_URL": "https://example.invalid"})
    assert result.returncode == 0, result.stdout + result.stderr
    for name in E2E_TEST_NAMES:
        assert name not in result.stdout


def test_azure_certification_command_collects_both_e2e_functions() -> None:
    """The ``pytest tests/e2e ...`` step of ``e2e-azure.yml`` -- the release
    gate's certification run -- must select both live-Azure tests, not zero
    (pytest exit 5)."""
    steps = re.findall(
        r"^\s+run: pytest (tests/e2e .+)$", E2E_WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert len(steps) == 1, "expected exactly one single-line `run: pytest tests/e2e ...` step"
    report_flags = ("--html", "--junitxml", "--self-contained-html")
    args = [a for a in shlex.split(steps[0]) if not a.startswith(report_flags)]
    result = _collect(*args)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in E2E_TEST_NAMES:
        assert name in result.stdout
