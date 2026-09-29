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
| `e2e-azure.yml` | real-Azure certification of one exact commit |
| `publish-pypi.yml` | the only path that uploads to PyPI (`workflow_dispatch` only) |

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

## Step 3: The release workflow runs

The tag starts `publish-pypi.yml`. Everything else is automatic:

```
build -> lib-tests -> doctor-runtime-gate -> azure-e2e -> publish
```

| Tier | Catches |
|---|---|
| `build` | tag/`__version__` mismatch; produces the one artifact that is later uploaded |
| `lib-tests` | library unit regressions |
| `doctor-runtime-gate` | installs the candidate wheel, asserts the installed version matches the release, then runs the package's own CLI (`azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal`) from the installed wheel. Unlike a host-boot smoke, this imports and exercises this package's primary runtime surface (the diagnostic CLI) end to end. |
| `azure-e2e` | cloud-only drift — deploys to real Azure, runs the live e2e suite, uploads an `azure-cert` record |
| `publish` | uploads the exact artifact `build` produced; it never rebuilds |

`azure-e2e` calls `e2e-azure.yml` as a reusable workflow at the same ref being published, so
certification covers the exact published commit by construction. There is no separate certification
step to dispatch and no freshness window to expire.

Publication uses PyPI Trusted Publishing (OIDC); there is no API token to manage.

To re-run after a failed gate (nothing was uploaded, so the version is still free):

```bash
gh workflow run publish-pypi.yml --ref main -f tag=v0.21.0
```

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
