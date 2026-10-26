from __future__ import annotations

import pytest

from azure_functions_doctor.profiles import profiles_for_rule, rule_matches_profile


def test_profiles_for_rule_returns_required_core_membership_in_profile_order() -> None:
    """Core gates belong to deployment preflight, not the developer-tooling-only profile."""
    # Given
    rule = {"id": "check_host_json", "required": True, "group": "core"}

    # When
    profiles = profiles_for_rule(rule)

    # Then
    assert profiles == ["minimal", "deploy", "full"]


def test_profiles_for_rule_limits_developer_rule_to_development_and_full() -> None:
    # Given
    rule = {"id": "check_venv", "required": False, "group": "core"}

    # When
    profiles = profiles_for_rule(rule)

    # Then
    assert profiles == ["development", "full"]


def test_rule_matches_profile_rejects_unknown_profile() -> None:
    # Given
    rule = {"id": "check_host_json", "required": True}

    # When / Then
    with pytest.raises(
        ValueError,
        match="^Profile must be one of: minimal, deploy, development, full$",
    ):
        rule_matches_profile(rule, "production")
