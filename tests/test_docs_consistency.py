"""Tests for the documentation-consistency guards (issue #354)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_docs_consistency.py"
RULES_JSON = ROOT / "src" / "azure_functions_doctor" / "assets" / "rules" / "v2.json"
README = ROOT / "README.md"


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
