# Release Process

This document describes how a new version of **azure-functions-doctor** reaches PyPI.

Releases are automated by [Release Please](https://github.com/googleapis/release-please). It decides the
version, writes the changelog, and cuts the tag. It does **not** publish — publication is a separate,
gated step.

---

## Who owns what

| Component | Owns |
|---|---|
| `release-please.yml` | version calculation, `CHANGELOG.md`, the Release PR, the tag, the GitHub Release |
| `release-please.yml` → `standardize-release-notes` | presentation of the GitHub Release body only (layout + credits, see [Release notes layout](#release-notes-layout-and-credits)) |
| `e2e-azure.yml` | real-Azure certification of one exact commit |
| `publish-pypi.yml` | the only path that uploads to PyPI (triggered by `v*` tag pushes; `workflow_dispatch` is the manual recovery entrypoint) |

**Do not hand-edit** `src/azure_functions_doctor/__init__.py` version strings, `CHANGELOG.md`, or
`.release-please-manifest.json`. Release Please maintains all three.

---

## Step 1: Merge Conventional Commits

Version bumps are derived from commit messages on `main`:

| Commit | Bump |
|---|---|
| `fix:` | patch (`0.20.0` → `0.20.1`) |
| `feat:` | minor (`0.20.0` → `0.21.0`) |
| `feat!:` / `fix!:` / `BREAKING CHANGE:` footer | minor while pre-1.0 (see below) |

While this package is pre-1.0, `bump-minor-pre-major` is enabled, so a breaking change moves to the
next minor (`0.21.0`) rather than jumping to `1.0.0`. Going to 1.0 is a deliberate, separate decision.

Use scopes for more context: `fix(scope): short imperative summary`

### Changelog categories

| Prefix | Changelog section |
|--------|--------------------|
| `feat:` | Features |
| `fix:` | Bug Fixes |
| `docs:` | Documentation |
| `refactor:` | Refactor |
| `style:` | Styling |
| `test:` | Testing |
| `perf:` | Performance |
| `ci:` / `chore:` | Miscellaneous Tasks |
| `build:` | Other |

These are configured in `release-please-config.json` under `changelog-sections`.

---

## Step 2: Merge the Release PR

Release Please keeps an open **Release PR** titled like `chore(main): release 0.21.0`. It contains the
version bump and the changelog entry.

Merging that PR is the act of cutting a release. On merge, Release Please tags the release commit
(`v0.21.0`) and publishes the GitHub Release.

Release Please runs with `RELEASE_PLEASE_TOKEN` (a fine-grained PAT) rather than the default
`GITHUB_TOKEN`, so the required status checks run on the Release PR and it is merged under the same
branch-protection rules as any other PR. The PAT expires; regenerate it and update the secret before
it does, or no Release PR will appear.

---

## Release cadence

**Default:** the maintainer batches routine user-facing changes into **at
most one planned release per week**, and only when the package is ready.
A quiet week requires no release. Ordinary development PRs continue to
merge when approved; Release Please keeps the open Release PR updated.
Merging that Release PR is a separate, explicit maintainer decision.

**Out-of-cycle:** dangerous false diagnostic guidance, sensitive diagnostic output, broken GitHub Action behavior, or failed tagged candidate may justify
an earlier patch. Before that merge, briefly document the affected users
and why it cannot wait. Do not add an automated waiting period or force
weekly releases just to satisfy a schedule.

Before a routine release, verify the newest **actual PyPI distribution**
separately from GitHub Release status, review the user-facing changes,
compatibility and migration notes, pending near-term fixes, and readiness
of all relevant package/consumer/Azure verification gates.
This repository additionally reviews CLI diagnostic accuracy and security, plus the separate rolling v1 GitHub Action major ref.
Preserve Release Please ownership of version/tags/CHANGELOG and keep all
existing tag-specific verification and publication gates intact.

---

## Step 3: The release workflow runs

The tag starts `publish-pypi.yml`. Everything else is automatic:

```
build -> lib-tests -> doctor-runtime-gate -> azure-e2e -> publish
```

| Tier | Catches |
|---|---|
| `build` | a tag that is not an ancestor of `origin/main`, or whose tagged `__version__` differs from the tag (`tools/audit_release_tags.py --tag`, then the existing tag/`__version__` check); produces the one artifact that is later uploaded |
| `lib-tests` | library unit regressions |
| `doctor-runtime-gate` | installs the candidate wheel, asserts the installed version matches the release, then runs the package's own CLI (`azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal`) from the installed wheel. Unlike a host-boot smoke, this imports and exercises this package's primary runtime surface (the diagnostic CLI) end to end. |
| `azure-e2e` | cloud-only drift — deploys to real Azure, runs the live e2e suite, uploads an `azure-cert` record |
| `publish` | uploads the exact artifact `build` produced; it never rebuilds |

`azure-e2e` calls `e2e-azure.yml` as a reusable workflow at the same ref being published, so
certification covers the exact published commit by construction. There is no separate certification
step to dispatch and no freshness window to expire.

Publication uses PyPI Trusted Publishing (OIDC); there is no API token to manage.

`publish-pypi.yml` runs automatically on every `v*` tag push. `workflow_dispatch` is its manual
recovery entrypoint — it takes **no inputs**; the workflow reads the version to verify from
`github.ref_name`, so the dispatch **ref** must be the existing tag itself:

To re-run the same, unchanged candidate after an external or transient gate failure (a flaky
Azure deploy, a PyPI outage, a runner hiccup), nothing was uploaded, so the version is still free:

```bash
gh workflow run publish-pypi.yml --ref v0.21.0
```

If the failure instead requires a code or workflow correction, fix forward on `main` and let the
next Release PR cut a new version — never move or reuse a tag to make a changed commit appear to
be the same release candidate.

---


## Release notes layout and credits

After Release Please creates the GitHub Release, the `standardize-release-notes` job rewrites
**only the Release body** with `tools/release_notes.py`. It does not create or move tags, does not
edit `CHANGELOG.md`, and runs separately from `publish-pypi.yml`, so it cannot block a release.
The items are the ones Release Please already generated, so the Release and `CHANGELOG.md` list
the same changes. The tool refuses to write if a PR or commit reference would be dropped.

Layout (empty sections are omitted):

1. `## vX.Y.Z (YYYY-MM-DD)`
2. Notes: status annotations such as "not published to PyPI"
3. Highlights
4. Breaking Changes, followed by the upgrade steps
5. Features, Bug Fixes, Performance, Reverts
6. New Contributors
7. A collapsed block for documentation, maintenance and other changes (historical releases only,
   because Release Please hides those types)
8. `**Full Changelog**` compare link

Credit rules:

- This is a primarily solo-maintained project: omit repetitive `by @yeongseon` on owner-authored changes, while retaining PR/issue references.
- Credit verified external human contributors with `by @username`, even when their PR was squash-merged by the owner. Confirm authorship from merged PRs, commits, or trusted GitHub noreply co-author trailers.
- Exclude bots and configured non-human accounts from human credits.
- Show **New Contributors** only for verified first merged contributions from external humans; omit the section for owner-only releases.

Release-specific statements that must never be lost (for example a release that was not
published) are listed under `protected` in `.github/release-notes.json`; the tool fails instead of
dropping them.

```bash
# Needs a token: export GH_TOKEN=$(gh auth token)
# Preview without changing anything
python3 -m tools.release_notes apply v0.23.1 --dry-run
# Re-render an already standardized release (it is skipped otherwise)
python3 -m tools.release_notes apply v0.23.1 --force --backup ./release-backup
```

Editing a historical Release never republishes a package and never touches the tag.

---

## What is no longer used

| Retired | Replacement |
|---|---|
| `make release-patch` / `release-minor` / `release-major` / `release` | merge the Release PR |
| `make changelog` / `make commit-changelog` (git-cliff) | Release Please writes `CHANGELOG.md` |
| `make tag-release` | Release Please creates the tag |
| `make publish-pypi` (local `hatch publish`) | the `publish` job in `publish-pypi.yml` |
| `cliff.toml` | `release-please-config.json` |
| manual Azure certification dispatch | the `azure-e2e` job in `publish-pypi.yml` |

These Makefile targets are **deleted**, not merely discouraged, so nothing can create a second writer
for the version, changelog, or tags — or push an ungated artifact to PyPI.

`make publish-test` (TestPyPI) is unaffected.

---

## Release tag audit

`tools/audit_release_tags.py` is a stdlib-only, **read-only** check (git data only; no network, token,
tag move or release edit). A `vX.Y.Z` tag is a package release tag and must satisfy both:

1. the version declared in the source **at the tagged commit** equals `X.Y.Z`
   (`src/azure_functions_doctor/__init__.py`; early history falls back to a static `pyproject.toml`
   `version`); and
2. the tagged commit is an ancestor of `origin/main`.

The moving GitHub Action major ref (`v1`, `v2`, ...) is classified as `action-ref`, is never compared
with a package version, and is not a Python package release.

```bash
python tools/audit_release_tags.py --tag v0.23.1      # gate mode; exits 1 on any defect
python tools/audit_release_tags.py --all [--json]     # version-by-version audit of every local tag
```

- **Gate mode** runs in the `build` job of `publish-pypi.yml` before a candidate is built, so a
  mismatched or off-main tag fails before any artifact exists. It never honours exceptions.
- **Audit mode** runs in the `quality` job of `ci-test.yml` (pull requests and `main`). Verified
  historical defects are listed in `KNOWN_EXCEPTIONS` in the tool, each pinned to the tagged commit
  SHA and the exact defect set, so a re-pointed tag or a *new* defect is still a failure. Add an
  exception only with evidence and a tracking issue; never to make a new release pass.
- The audit does not query PyPI or GitHub Releases. A successful GitHub Release is not proof of
  distribution: confirm PyPI separately (`https://pypi.org/pypi/azure-functions-doctor/json`).
- A rejected tag is a failed candidate, not a reason to move it. Follow the [Recovery](#recovery) table:
  fix forward and let Release Please cut the next version.

---

## Recovery

| Situation | Action |
|---|---|
| Any gate failed | Nothing was uploaded. Fix the cause and re-run `publish-pypi.yml` on the same tag, or fix forward on `main` and let the next Release PR cut a new version. Never move or reuse a tag. |
| Tag exists but was never published | A valid resting state. Re-run publish, or abandon the version and let the next release take the following number. |
| Release PR stopped appearing | Check for a stale `autorelease: pending` label on an already-merged Release PR. Release Please treats that as a release in flight and will not open another. This failure is silent — the workflow still reports success. |
| Automation unavailable (break-glass) | Bump `__version__`, match `.release-please-manifest.json`, commit, tag, push. The tag starts the same gated workflow — never bypass it. |

---

## Still-current Makefile commands

| Task | Command |
|------|---------|
| Build distributions | `make build` |
| Publish to TestPyPI | `make publish-test` |
| Show current version | `make version` |

To test a local build:

```bash
pip install dist/azure_functions_doctor-<version>-py3-none-any.whl
```

---

## Related

- [CHANGELOG.md](https://github.com/yeongseon/azure-functions-doctor-python/blob/main/CHANGELOG.md)
- [Development Guide](development.md)
- [Contributing](contributing.md)
- [Release Please](https://github.com/googleapis/release-please)
