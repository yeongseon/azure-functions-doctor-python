"""Rule-profile membership logic (issue #356).

This module is intentionally dependency-free (no ``jsonschema`` or handler
imports) so that lightweight tooling — such as
``scripts/gen_rule_inventory.py`` running under a docs-only CI environment —
can derive profile membership without importing the full diagnostic runner.
``doctor.py`` re-exports these names so the runtime filtering and the generated
rule inventory share a single source of truth.
"""

from __future__ import annotations

from typing import Mapping

# Rules that validate the local developer environment rather than the deployed
# application's runtime/hosting correctness.
DEV_ENVIRONMENT_RULES: frozenset[str] = frozenset(
    {
        "check_venv",
        "check_python_executable",
        "check_func_cli",
        "check_func_core_tools_version",
        "check_local_settings",
    }
)

# Selectable rule profiles, ordered from narrowest to widest surface.
PROFILE_NAMES: tuple[str, ...] = ("minimal", "deploy", "development", "full")


def rule_matches_profile(rule: Mapping[str, object], profile: str) -> bool:
    """Return whether ``rule`` runs under the given ``profile``.

    - ``full``: every rule.
    - ``minimal``: required (gating) rules only.
    - ``deploy``: core-group rules covering Azure runtime/hosting/deployment
      correctness; developer-environment and integration rules are excluded.
    - ``development``: developer-environment checks (virtual environment, Python
      executable, Core Tools, local.settings existence).
    """
    if profile == "full":
        return True
    if profile == "minimal":
        return bool(rule.get("required", True))
    if profile == "development":
        return rule.get("id") in DEV_ENVIRONMENT_RULES
    if profile == "deploy":
        return rule.get("group", "core") == "core" and rule.get("id") not in DEV_ENVIRONMENT_RULES
    raise ValueError("Profile must be one of: " + ", ".join(PROFILE_NAMES))


def profiles_for_rule(rule: Mapping[str, object]) -> list[str]:
    """Return the profile names ``rule`` participates in, widest-last."""
    return [name for name in PROFILE_NAMES if rule_matches_profile(rule, name)]
