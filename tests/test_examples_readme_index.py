"""Docs consistency: ``examples/README.md`` must index every example under ``examples/v2``.

Checks only file names and paths; it runs no diagnostics. The result of each example is covered by
``tests/test_examples.py``.
"""

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_README = REPO_ROOT / "examples" / "README.md"
EXAMPLES_DIR = REPO_ROOT / "examples" / "v2"

# Examples whose rule is named in both the index table and the example's own README.
EXAMPLE_RULES = [
    ("broken-flex-runtime-config", "check_flex_runtime_config"),
    ("broken-flex-deprecated-settings", "check_flex_deprecated_settings"),
    ("broken-flex-deployment-storage", "check_flex_deployment_storage"),
    ("broken-dev-storage-leak", "check_dev_storage_connection"),
    ("broken-legacy-extension-version", "check_functions_extension_version"),
]


def _listed_paths() -> set[str]:
    text = EXAMPLES_README.read_text(encoding="utf-8")
    return set(re.findall(r"`examples/v2/([\w.-]+)`", text))


def test_every_listed_example_path_exists() -> None:
    missing = sorted(name for name in _listed_paths() if not (EXAMPLES_DIR / name).is_dir())

    assert missing == [], f"examples/README.md lists examples that do not exist: {missing}"


def test_every_example_directory_is_listed() -> None:
    on_disk = {path.name for path in EXAMPLES_DIR.iterdir() if path.is_dir()}

    unlisted = sorted(on_disk - _listed_paths())

    assert unlisted == [], f"examples/README.md does not list: {unlisted}"


@pytest.mark.parametrize(("example", "rule"), EXAMPLE_RULES)
def test_index_and_example_readme_name_the_same_rule(example: str, rule: str) -> None:
    index_row = next(
        line
        for line in EXAMPLES_README.read_text(encoding="utf-8").splitlines()
        if f"`examples/v2/{example}`" in line
    )
    example_readme = (EXAMPLES_DIR / example / "README.md").read_text(encoding="utf-8")

    assert f"`{rule}`" in index_row, f"{example}: index row does not name {rule}"
    assert f"`{rule}`" in example_readme, f"{example}: its README does not name {rule}"
