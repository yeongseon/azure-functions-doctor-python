"""Regression guard for the release-gate drift-lint.

Exercises tools/lint_release_workflows.py against this repo (must be clean) and
against synthetic drift (must be caught). Keeps the vendored lint honest.

Family-agnostic: the runtime-tier assertions are derived from the lint's own
``REQUIRED_RUNTIME_TIERS`` config, so this same test file is valid across the
cookbook / runtime-gate / minimal repo families.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LINT_PATH = _REPO_ROOT / "tools" / "lint_release_workflows.py"

_spec = importlib.util.spec_from_file_location("lint_release_workflows", _LINT_PATH)
assert _spec and _spec.loader
lint_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_mod)


def _needs(*extra: str) -> str:
    """Build a ``publish`` job stub with the universal needs plus ``extra``."""
    items = list(lint_mod.UNIVERSAL_REQUIRED_NEEDS) + list(extra)
    return f"  publish:\n    needs: [{', '.join(items)}]\n"


def test_repo_release_workflows_are_clean() -> None:
    """The committed gate workflows must satisfy the canonical pins + gate."""
    assert lint_mod.lint() == []


def test_detects_non_canonical_pin() -> None:
    text = "      - uses: actions/checkout@" + "0" * 40 + " # v7.0.1\n"
    errors = lint_mod.check_pins(text, "fake.yml")
    assert errors and "expected canonical" in errors[0]


def test_detects_annotation_drift() -> None:
    sha, _ = lint_mod.CANONICAL_ACTIONS["actions/checkout"]
    text = f"      - uses: actions/checkout@{sha} # v6\n"
    errors = lint_mod.check_pins(text, "fake.yml")
    assert errors and "annotation" in errors[0]


def test_detects_unpinned_tag() -> None:
    text = "      - uses: actions/checkout@v7.0.1\n"
    errors = lint_mod.check_pins(text, "fake.yml")
    assert errors and "not pinned to a 40-hex SHA" in errors[0]


def test_detects_missing_azure_e2e_gate() -> None:
    # Drop azure-e2e while keeping build + lib-tests + tiers.
    tiers = ", ".join(lint_mod.REQUIRED_RUNTIME_TIERS)
    joined = "build, lib-tests" + (f", {tiers}" if tiers else "")
    text = f"  publish:\n    needs: [{joined}]\n"
    errors = lint_mod.check_publish_needs(text, "publish-pypi.yml")
    assert any("azure-e2e" in e for e in errors)


def test_detects_regressed_needs() -> None:
    text = "  publish:\n    needs: [build, lib-tests]\n"
    errors = lint_mod.check_publish_needs(text, "publish-pypi.yml")
    assert any("regressed to build+lib-tests" in e for e in errors)


@pytest.mark.skipif(
    not lint_mod.REQUIRED_RUNTIME_TIERS,
    reason="minimal family has no required runtime tier",
)
def test_detects_missing_runtime_tier() -> None:
    # Universal needs present but the family-required runtime tier missing.
    text = _needs()
    errors = lint_mod.check_publish_needs(text, "publish-pypi.yml")
    assert any("runtime tier" in e for e in errors)


def test_parses_block_style_needs() -> None:
    all_needs = list(lint_mod.UNIVERSAL_REQUIRED_NEEDS) + list(lint_mod.REQUIRED_RUNTIME_TIERS)
    body = "  publish:\n    needs:\n"
    for item in all_needs:
        body += f"      - {item}\n"
    body += "    runs-on: ubuntu-latest\n"
    assert lint_mod.check_publish_needs(body, "publish-pypi.yml") == []
