#!/usr/bin/env python3
"""Synchronize documentation version strings with the canonical ``__version__``.

The release process bumps ``__version__`` in
``src/azure_functions_doctor/__init__.py`` but the AI-assistant/docs surface
(``llms.txt``, ``llms-full.txt``, ``docs/deployment.md`` and ``README.md``)
carries hard-coded version strings that ``scripts/check_docs_consistency.py``
enforces on CI. Without this script those files must be edited by hand on every
release, which repeatedly turned the ``test (3.10)`` leg red.

This script rewrites every package-version reference in those files to match the
current ``__version__`` and is safe to run repeatedly (idempotent). It never
touches the unrelated SARIF schema version (``"version": "2.1.0"``): the SARIF
driver's package version is matched only when anchored to the
``"name": "azure-functions-doctor"`` line.

Usage:
    python scripts/sync_docs_version.py           # rewrite docs in place
    python scripts/sync_docs_version.py --check    # exit 1 if any file is stale
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
INIT_PY = ROOT / "src" / "azure_functions_doctor" / "__init__.py"

_SEMVER = r"\d+\.\d+\.\d+"


def _read_version() -> str:
    text = INIT_PY.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        raise SystemExit(f"Could not find __version__ in {INIT_PY}")
    return match.group(1)


def _substitutions(version: str) -> dict[str, list[tuple[str, str]]]:
    """Map each doc file to its ``(pattern, replacement)`` rewrite rules."""
    return {
        "llms.txt": [
            (rf"(?m)^- Version: {_SEMVER}$", f"- Version: {version}"),
        ],
        "llms-full.txt": [
            (rf"(?m)^- Version: {_SEMVER}$", f"- Version: {version}"),
            (rf'"tool_version": "{_SEMVER}"', f'"tool_version": "{version}"'),
            (
                rf'("name": "azure-functions-doctor",\s*"version": ")({_SEMVER})(")',
                rf"\g<1>{version}\g<3>",
            ),
        ],
        "docs/deployment.md": [
            (rf"Doctor CLI v{_SEMVER}", f"Doctor CLI v{version}"),
            (rf'"tool_version": "{_SEMVER}"', f'"tool_version": "{version}"'),
            (
                rf'("name": "azure-functions-doctor",\s*"version": ")({_SEMVER})(")',
                rf"\g<1>{version}\g<3>",
            ),
        ],
        "README.md": [
            (rf"package version \({_SEMVER}\)", f"package version ({version})"),
            (
                rf"yeongseon/azure-functions-doctor@v{_SEMVER}",
                f"yeongseon/azure-functions-doctor@v{version}",
            ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if any doc file would change.",
    )
    args = parser.parse_args()

    version = _read_version()
    stale: list[str] = []

    for rel_path, rules in _substitutions(version).items():
        path = ROOT / rel_path
        original = path.read_text(encoding="utf-8")
        updated = original
        for pattern, replacement in rules:
            updated = re.sub(pattern, replacement, updated)
        if updated != original:
            stale.append(rel_path)
            if not args.check:
                path.write_text(updated, encoding="utf-8")

    if args.check:
        if stale:
            print("Documentation version references are stale:")
            for rel_path in stale:
                print(f"  - {rel_path}")
            print(f"Fix with: python scripts/sync_docs_version.py (target {version})")
            return 1
        print(f"Documentation version references already match {version}.")
        return 0

    if stale:
        print(f"Synced version references to {version} in: " + ", ".join(stale))
    else:
        print(f"Version references already match {version}; nothing to do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
