"""Tests for the documentation-consistency guards (issue #354)."""

import importlib.util
import json
from pathlib import Path
import re
from types import ModuleType

from typer.core import TyperGroup, TyperOption
from typer.main import get_command

from azure_functions_doctor.cli import SUPPORTED_DEPLOYMENT_MODES, cli
from azure_functions_doctor.target_resolver import SUPPORTED_HOSTING_PLANS

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_docs_consistency.py"
RULES_JSON = ROOT / "src" / "azure_functions_doctor" / "assets" / "rules" / "v2.json"
README = ROOT / "README.md"
USAGE = ROOT / "docs" / "usage.md"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_docs_consistency", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rule_count() -> int:
    return len(json.loads(RULES_JSON.read_text(encoding="utf-8")))


class TestReadmeRuleCount:
    def test_readme_count_matches_ruleset(self) -> None:
        module = _load_module()
        assert module._check_readme_rule_count() == []

    def test_readme_states_exact_current_count(self) -> None:
        content = README.read_text(encoding="utf-8")
        assert f"**{_rule_count()} diagnostic checks**" in content

    def test_guard_flags_stale_count(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        module = _load_module()
        # Simulate a ruleset that grew without the README being updated.
        monkeypatch.setattr(module, "_rule_ids_from_json", lambda: {f"r{i}" for i in range(999)})
        errors = module._check_readme_rule_count()
        assert errors
        assert "does not" in errors[0]

    def test_guard_flags_missing_count_phrase(self, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
        module = _load_module()
        fake_readme = tmp_path / "README.md"
        fake_readme.write_text("no count here", encoding="utf-8")
        monkeypatch.setattr(module, "ROOT", tmp_path)
        errors = module._check_readme_rule_count()
        assert errors
        assert "could not find" in errors[0]

    def test_full_check_passes(self) -> None:
        module = _load_module()
        assert module.main() == 0


def test_usage_option_reference_matches_doctor_help() -> None:
    # Given: the documented full option table and the live doctor command
    usage = USAGE.read_text()
    option_table = usage[usage.index("## Full option reference") : usage.index("!!! note")]
    documented = set(re.findall(r"--[a-z][\w-]+", option_table))

    # When: the doctor command's Click options are inspected directly
    root_command = get_command(cli)
    assert isinstance(root_command, TyperGroup)
    doctor_command = root_command.commands["doctor"]
    help_options = {
        option
        for param in doctor_command.params
        if isinstance(param, TyperOption)
        for option in (*param.opts, *param.secondary_opts)
        if option.startswith("--")
    } - {"--no-debug"}

    # Then: every long command option is present in the full reference
    assert documented == help_options


def test_usage_documents_all_context_values() -> None:
    # Given: the deployment context values accepted by the CLI
    usage = USAGE.read_text()

    # When: the full option reference is inspected
    deployment_row = usage.split("| `--deployment-mode`")[1].splitlines()[0]
    hosting_row = usage.split("| `--hosting-plan`")[1].splitlines()[0]
    deployment_values = set(re.findall(r"`([\w-]+)`", deployment_row))
    hosting_values = set(re.findall(r"`([\w-]+)`", hosting_row))

    # Then: both option rows list every accepted value
    assert deployment_values == set(SUPPORTED_DEPLOYMENT_MODES)
    assert hosting_values == set(SUPPORTED_HOSTING_PLANS)
