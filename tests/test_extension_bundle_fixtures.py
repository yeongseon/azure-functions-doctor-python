"""Positive/negative on-disk fixture pair for ``check_extension_bundle_v4`` (issue #659).

Gap audited: the v4 bundle-range rule was covered only by handler-level tests that write a
temporary ``host.json``. These two tiny synthetic projects exercise the same rule end to end
through ``Doctor`` and the CLI, and pin the rule id, severity and remediation text.

Run only these tests locally::

    pytest tests/test_extension_bundle_fixtures.py --no-cov
"""

from pathlib import Path

from typer.testing import CliRunner

from azure_functions_doctor.cli import cli
from azure_functions_doctor.doctor import CheckResult, Doctor

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "v2"
SUPPORTED = FIXTURES_DIR / "extension_bundle_v4_supported"
OVERBROAD = FIXTURES_DIR / "extension_bundle_v4_overbroad"
RULE_ID = "check_extension_bundle_v4"
RECOMMENDED_RANGE = "[4.*, 5.0.0)"

runner = CliRunner()


def _items(project: Path) -> dict[str, CheckResult]:
    results = Doctor(str(project)).run_all_checks()
    return {item["rule_id"]: item for section in results for item in section["items"]}


def test_supported_v4_range_passes_without_false_positive() -> None:
    items = _items(SUPPORTED)
    assert items["check_extension_bundle"]["status"] == "pass"
    assert items[RULE_ID]["status"] == "pass"
    assert RECOMMENDED_RANGE in items[RULE_ID]["value"]


def test_overbroad_v4_range_warns_with_stable_id_severity_and_remediation() -> None:
    item = _items(OVERBROAD)[RULE_ID]
    assert item["status"] == "warn"
    assert item["severity"] == "warning"
    assert "[4.0.0, 6.0.0)" in item["value"]
    assert "exclusive 5.0.0" in item["value"]
    assert RECOMMENDED_RANGE in item["hint"]
    assert "Microsoft.Azure.Functions.ExtensionBundle" in item["hint"]


def test_overbroad_range_is_advisory_and_does_not_fail_the_run() -> None:
    # The bundle rule is optional: it warns but must not gate the CLI exit code.
    # Only this rule's behavior is asserted; environment-dependent checks are not.
    items = _items(OVERBROAD)
    assert items["check_extension_bundle"]["status"] == "pass"
    assert items[RULE_ID]["status"] == "warn"
    assert not [rule for rule, item in items.items() if item["status"] == "fail"]
    result = runner.invoke(cli, ["doctor", "--path", str(OVERBROAD), "--profile", "minimal"])
    assert result.exit_code == 0
