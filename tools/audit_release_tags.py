#!/usr/bin/env python3
"""Read-only audit of Doctor release tags against their package source.

A ``vX.Y.Z`` tag is a *package* release tag. It is only trustworthy when:

1. the package version declared in the source **at the tagged commit**
   (``src/azure_functions_doctor/__init__.py``, falling back to a static
   ``version =`` in ``pyproject.toml`` for early history) equals ``X.Y.Z``; and
2. the tagged commit is an ancestor of the release branch (``main``), so the
   tag belongs to the ordinary release lineage rather than a divergent branch.

The moving GitHub Action major ref (``v1``, ``v2`` ...) is **not** a package
release and is classified separately; it is never compared against a package
version. Any other tag shape is reported as unrecognized.

Two modes (both strictly read-only; no tag, ref or release is created, moved or
deleted, and no network or token is used):

* ``--tag vX.Y.Z``   gate mode, used by ``publish-pypi.yml`` before a candidate
  is built. Historical exceptions are deliberately **not** honoured here: a
  tag being published must always satisfy both checks.
* ``--all``          deterministic version-by-version audit of every local tag.
  Previously verified historical defects are listed in ``KNOWN_EXCEPTIONS`` and
  reported as ``exception``; any *new* defect is reported as ``FAIL`` and makes
  the exit code non-zero.

Exceptions are keyed by tag **and** pinned to the tagged commit SHA, so moving
or recreating a registered tag invalidates the exception instead of hiding it.

Stdlib-only on purpose. Exit code 0 = clean, 1 = defect found, 2 = usage/git error.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys

VERSION_FILE = "src/azure_functions_doctor/__init__.py"
PYPROJECT_FILE = "pyproject.toml"

_PACKAGE_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
_ACTION_REF_RE = re.compile(r"^v\d+$")
_INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*"(?P<v>[^"]+)"', re.MULTILINE)
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"(?P<v>[^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class KnownException:
    """A historical tag defect that was verified and is tracked elsewhere."""

    commit: str
    defects: frozenset[str]
    reason: str


# Defect codes: "version-mismatch", "not-on-main", "no-source-version".
# Only evidence-backed entries belong here; see docs/release_tag_audit.md.
KNOWN_EXCEPTIONS: dict[str, KnownException] = {
    "v0.1.1": KnownException(
        commit="916ee3d1b4d643192a9bcad2896a1b8d498c6482",
        defects=frozenset({"version-mismatch"}),
        reason=(
            "tagged source still declares 0.1.0 and PyPI has no 0.1.1 files "
            "(early history; see #671 and docs/release_tag_audit.md)"
        ),
    ),
    "v0.16.4": KnownException(
        commit="2e45245f3f390e19ea56de6238c6a24cc8a2f450",
        defects=frozenset({"version-mismatch", "not-on-main"}),
        reason=(
            "tagged source declares 0.16.2, the commit is not on main, and PyPI "
            "has no 0.16.4 files (see #670 and docs/release_tag_audit.md)"
        ),
    ),
}


@dataclass
class TagReport:
    tag: str
    kind: str  # "package" | "action-ref" | "unrecognized"
    commit: str
    source_version: str | None
    on_main: bool | None
    defects: list[str]
    excepted: bool
    note: str

    @property
    def status(self) -> str:
        if self.kind == "action-ref":
            return "action-ref"
        if not self.defects:
            return "ok"
        return "exception" if self.excepted else "FAIL"

    def as_dict(self) -> dict[str, object]:
        return {
            "tag": self.tag,
            "kind": self.kind,
            "commit": self.commit,
            "source_version": self.source_version,
            "on_main": self.on_main,
            "status": self.status,
            "defects": self.defects,
            "note": self.note,
        }


class GitError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def parse_source_version(init_text: str | None, pyproject_text: str | None) -> str | None:
    """Return the declared package version, preferring ``__version__``."""
    if init_text:
        match = _INIT_VERSION_RE.search(init_text)
        if match:
            return match.group("v")
    if pyproject_text:
        match = _PYPROJECT_VERSION_RE.search(pyproject_text)
        if match:
            return match.group("v")
    return None


def _show(repo: Path, commit: str, path: str) -> str | None:
    try:
        return _git(repo, "show", f"{commit}:{path}")
    except GitError:
        return None


def _is_ancestor(repo: Path, commit: str, main_ref: str) -> bool:
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, main_ref],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise GitError(f"cannot compare {commit} with {main_ref}: {proc.stderr.strip()}")


def audit_tag(
    repo: Path,
    tag: str,
    main_ref: str,
    *,
    honour_exceptions: bool,
    exceptions: dict[str, KnownException] | None = None,
) -> TagReport:
    """Audit one tag. Raises ``GitError`` if the tag or ``main_ref`` is unusable."""
    registry = KNOWN_EXCEPTIONS if exceptions is None else exceptions
    commit = _git(repo, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}").strip()

    if _ACTION_REF_RE.match(tag):
        return TagReport(
            tag, "action-ref", commit, None, None, [], False,
            "moving GitHub Action major ref; not a package release",
        )  # fmt: skip
    package = _PACKAGE_TAG_RE.match(tag)
    if not package:
        return TagReport(
            tag, "unrecognized", commit, None, None, ["unrecognized-tag"], False,
            "tag is neither vX.Y.Z (package) nor vN (Action ref)",
        )  # fmt: skip

    expected = package.group("version")
    declared = parse_source_version(
        _show(repo, commit, VERSION_FILE), _show(repo, commit, PYPROJECT_FILE)
    )
    on_main = _is_ancestor(repo, commit, main_ref)

    defects: list[str] = []
    notes: list[str] = []
    if declared is None:
        defects.append("no-source-version")
        notes.append("no package version found in the tagged source")
    elif declared != expected:
        defects.append("version-mismatch")
        notes.append(f"tag says {expected} but the tagged source declares {declared}")
    if not on_main:
        defects.append("not-on-main")
        notes.append(f"tagged commit is not an ancestor of {main_ref}")

    excepted = False
    known = registry.get(tag)
    if honour_exceptions and known and defects:
        # Pinned to the commit and to the exact defect set: anything new, or a
        # re-pointed tag, stays a failure.
        excepted = known.commit == commit and set(defects) <= known.defects
        if excepted:
            notes.append(f"known historical exception: {known.reason}")
    return TagReport(tag, "package", commit, declared, on_main, defects, excepted, "; ".join(notes))


def list_tags(repo: Path) -> list[str]:
    out = _git(repo, "for-each-ref", "--format=%(refname:strip=2)", "refs/tags")
    return sorted(
        (t for t in out.splitlines() if t),
        key=lambda t: [int(p) if p.isdigit() else 0 for p in re.split(r"[.v]", t)],
    )


def render_table(reports: list[TagReport]) -> str:
    rows = [("TAG", "STATUS", "SOURCE", "ON-MAIN", "COMMIT", "NOTE")]
    for r in reports:
        on_main = "-" if r.on_main is None else ("yes" if r.on_main else "NO")
        rows.append((r.tag, r.status, r.source_version or "-", on_main, r.commit[:12], r.note))
    widths = [max(len(row[i]) for row in rows) for i in range(5)]
    return "\n".join(
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row[:5])) + "  " + row[5]
        for row in rows
    ).rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tag", help="gate mode: validate one tag (no exceptions)")
    mode.add_argument("--all", action="store_true", help="audit every local tag")
    parser.add_argument("--main-ref", default="origin/main", help="release branch ref")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository path")
    parser.add_argument("--json", action="store_true", help="emit JSON (with --all)")
    args = parser.parse_args(argv)

    try:
        if args.tag:
            report = audit_tag(args.repo, args.tag, args.main_ref, honour_exceptions=False)
            if report.kind != "package":
                print(
                    f"::error ::{args.tag} is not a vX.Y.Z package release tag ({report.note})",
                    file=sys.stderr,
                )
                return 1
            if report.defects:
                print(f"::error ::Release tag {args.tag} rejected: {report.note}", file=sys.stderr)
                return 1
            print(
                f"{args.tag}: source version {report.source_version} matches and "
                f"{report.commit[:12]} is on {args.main_ref}"
            )
            return 0

        reports = [
            audit_tag(args.repo, t, args.main_ref, honour_exceptions=True)
            for t in list_tags(args.repo)
        ]
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failed = [r for r in reports if r.status == "FAIL"]
    if args.json:
        print(json.dumps([r.as_dict() for r in reports], indent=2, sort_keys=True))
    else:
        print(render_table(reports))
        print(
            f"\n{len(reports)} tags: "
            f"{sum(r.status == 'ok' for r in reports)} ok, "
            f"{sum(r.status == 'exception' for r in reports)} known exceptions, "
            f"{sum(r.status == 'action-ref' for r in reports)} action refs, "
            f"{len(failed)} FAIL"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
