# AGENTS.md

## Purpose
`azure-functions-doctor` is a Python CLI that diagnoses common Azure Functions project issues.

## Repository Identity

- Project: `azure-functions-doctor`
- Project type: Python library and CLI
- Runtime scope: Azure Functions Python v2 programming model
- Minimum supported Python: `3.10`
- Packaging: `pyproject.toml` with Hatch

## Root vs Docs

Use the repository root for engineering and planning documents:

- `AGENTS.md`: contribution and automation rules
- `DESIGN.md`: architecture and design principles
- `PRD.md`: product scope and user-facing goals

Use `docs/` for user-facing documentation only:

- installation
- usage
- API reference
- examples
- diagnostics and guides

If a change materially affects behavior, architecture, or project positioning, update the
relevant root document in the same pull request or commit series.

## Read First
- `README.md`
- `CONTRIBUTING.md`
- `docs/agent-playbook.md`

## Working Rules

### Test Coverage
- Maintain test coverage at **95% or above** for committed changes and PRs.
- Run `hatch run pytest --cov --cov-report=term-missing -q` to verify before submitting changes.
- Any PR that drops coverage below 95% must include additional tests to compensate.
- Keep diagnostics deterministic and user-facing messages actionable.
- Prefer extending existing rule patterns over introducing one-off flows.
- If a CLI option or exit code changes, update docs and tests in the same change.
- Preserve Python 3.10+ compatibility declared in `pyproject.toml`.

### Documentation & Translations
- English (`README.md`) is the **canonical** source of truth for all documentation. Translated READMEs (`README.ko.md`, `README.ja.md`, `README.zh-CN.md`) are **best-effort**, community-maintained, and may lag the English source.
- Translation sync is **not** required in the same PR as an English change, and a PR is **never** blocked by translation drift. Update translations opportunistically; when you do, keep them faithful to the current English source.
- Each translated README carries a staleness banner linking back to the canonical English README. Keep that banner in place so readers always know the translation may be out of date.

### Action Pinning
- All external `uses:` references in `.github/workflows/` must be SHA-pinned per `CONTRIBUTING.md` § "GitHub Actions Pinning". The PyPA publish action, local composite actions (`uses: ./...`), and the end-user `azure-functions-preflight.yml` template are the only documented exceptions and must carry an inline comment at the call site.

## Issue Conventions

Follow these conventions when opening issues so the backlog stays consistent with sibling DX Toolkit repositories.

### Title

Titles for issues, pull requests, and commits follow the **Title Convention** in [`CONTRIBUTING.md`](CONTRIBUTING.md#title-convention), the single source of truth for the format and the allowed types.

### Body

Use the following sections, in order, omitting any that do not apply:

```
## Context
What problem this issue addresses and why now. Note the target release (e.g. vX.Y.Z) here if known.

## Acceptance Checklist
- [ ] Concrete, verifiable items.

## Out of scope
- Items intentionally excluded, with links to the issues that track them.

## References
- PRs, ADRs, sibling issues, external docs.
```

### Labels

- Apply at least one type label: `bug`, `enhancement`, `documentation`, or `chore` (`ci`, `test`, `question` where they fit).
- Every new issue gets `needs-triage` (issue forms and the `Triage new issues` workflow add it automatically; add it yourself with `gh issue create --label needs-triage` when creating issues from a workflow). Leave it for the maintainer, who removes it after confirming validity, scope, type, and priority.
- Priority uses exactly one of `priority:critical` / `priority:high` / `priority:medium` / `priority:low`. Never write P0/P1/P2.
  - `critical` — fix now: security issue, data loss, broken released package, or blocked release pipeline.
  - `high` — address before the next planned release; serious impact or no reasonable workaround.
  - `medium` — normal planned work; a workaround exists or scope is limited.
  - `low` — opportunistic polish or non-urgent improvement.
- Priority may be provisional while `needs-triage` is present. An external contributor without label permissions should describe urgency in the issue body.
- Add `area:*` labels when they exist in the repository.
- Use `blocker` only when the issue blocks a release.
- There is no work-in-progress label. Open unfinished pull requests as Draft PRs, and link the issue with `Fixes #N` so its in-progress state shows on the issue.

### Umbrella issues

When splitting a large piece of work into focused issues, keep the umbrella open as a tracker that links each child issue with a checkbox; close it once every child is closed or explicitly deferred.

### Project management model

This repository is **issue-based, not milestone-based**. Track and group work using issues plus the existing label taxonomy — do **not** introduce parallel structures.

- Plan and group multi-issue efforts with an **umbrella tracker issue** (see above) plus the existing `priority:*` labels. Do **not** create GitHub Milestones — none exist by design, and their absence is an intentional signal, not an oversight.
- Do **not** invent new label taxonomies (e.g. `epic:*`, `vNext`, release-tag labels) to group work. Reuse `priority:*`, `area:*` (only where they already exist), and the umbrella issue. Propose any new label in discussion and wait for explicit approval before creating it.
- Treat optional or tentative suggestions ("we could…", "it might be nice to…", "it would be okay to…") as **discussion, not a directive**. Confirm intent before making any structural change to how work is tracked (milestones, labels, project boards, issue hierarchies).
- Before adding any organizational structure, check whether the repository already has an established convention. A category being empty or unused (zero milestones, no `epic:*` labels) is evidence to follow the existing pattern, not to introduce a new one.

## Validation
- `make test`
- `make lint`
- `make typecheck`
- `make build`

## Release Process

Three tools, one job each. Nothing else participates.

| Tool | Owns |
|---|---|
| **Release Please** | version decision, `__version__`, `CHANGELOG.md`, Release PR, tag, GitHub Release |
| **GitHub Actions** | verification, real-Azure e2e, PyPI publish |
| **Hatch** | building the Python package (reads `__version__` from `src/azure_functions_doctor/__init__.py`) |

- **Do NOT manually edit version strings, `CHANGELOG.md`, `.release-please-manifest.json`, or tags.** Release Please owns all of them. The public-API test reads `__version__` against `importlib.metadata.version(...)`, so no test changes are needed when bumping.
- Releases are driven by **Conventional Commits** on `main`, but only **user-facing** types cut one: `fix:` → patch, `perf:`/`revert:` → patch, `feat:` → minor, `feat!:`/`fix!:`/`BREAKING CHANGE:` → breaking. While this package is pre-1.0, `bump-minor-pre-major` keeps a breaking change on the `0.x` line.
- **`docs:`, `ci:`, `chore:`, `test:`, `build:`, `style:` and `refactor:` do not cut a release.** They are marked `"hidden": true` in `release-please-config.json`, which keeps them out of `CHANGELOG.md`; when a batch of commits contains nothing else, the release notes render empty and Release Please logs `No user facing commits found since <sha> - skipping` and opens no Release PR. Merging such a PR and seeing no version change is the intended outcome, not a broken pipeline. A breaking change still releases whatever its type is.
- There are **no release Makefile targets**. `make release-*`, `make changelog`, `make tag-release`, and `make publish-pypi` were deleted; a local `hatch publish` would have skipped every gate below.

### Flow

```
feat:/fix: PR merged into main
        |
  Release Please  ->  Release PR (version + CHANGELOG)
        |  maintainer reviews and merges
  tag vX.Y.Z + GitHub Release
        |
  publish-pypi.yml  (started by the tag)
        build -> lib-tests -> doctor-runtime-gate
              -> azure-e2e -> PyPI
```

1. Merge Conventional-Commit PRs into `main`. Release Please keeps an open **Release PR** showing exactly what the next release would be.
2. Merging that Release PR is the act of cutting a release.
3. Release Please tags the release commit and publishes the GitHub Release. The tag starts `publish-pypi.yml`.
4. Every verification tier runs in that one workflow. PyPI upload happens only if all of them pass.
5. Update `docs/changelog.md` separately if needed. It holds hand-maintained version history and migration notes, and Release Please does not touch it.

**Certification is an in-chain gate.** `azure-e2e` deploys to real Azure and runs the live e2e suite at the same ref being published, so it covers the exact published commit by construction. There is no separate certification step to dispatch, and no cross-run SHA or freshness matching to get wrong.

**`RELEASE_PLEASE_TOKEN` is load-bearing.** It is a fine-grained PAT stored as a repository secret. The default `GITHUB_TOKEN` cannot trigger other workflows, which would leave the Release PR without the required status checks — permanently unmergeable — and would stop the tag from starting `publish-pypi.yml`. The PAT grants repository write only; PyPI upload uses OIDC Trusted Publishing and cannot be reached with it. **Fine-grained PATs expire**: when it does, no Release PR appears. Regenerate it and update the secret before the expiry date.

### Tiered runtime verification (what gates a release)

Every tier runs inside `publish-pypi.yml` on the tag, and **all of them gate the upload**:

| Tier | Catches |
| --- | --- |
| `build` | tag/`__version__` mismatch; produces the one artifact that is later uploaded |
| `lib-tests` | library unit regressions |
| `doctor-runtime-gate` | installs the candidate wheel, asserts the installed version matches the release, then runs the package's own CLI (`azure-functions-doctor doctor --path examples/v2/http-trigger --profile minimal`) from the installed wheel. Unlike a host-boot smoke, this imports and exercises this package's primary runtime surface (the diagnostic CLI) end to end. |
| `azure-e2e` | cloud-only drift — deploys to real Azure, runs the live e2e suite, uploads an `azure-cert` record |
| `publish` | uploads the exact artifact `build` produced; it never rebuilds |

### Recovery
- **Any gate failed.** Nothing was uploaded, so the version is still free. Fix the cause and re-run the workflow on the same tag (`gh workflow run publish-pypi.yml --ref main -f tag=vX.Y.Z`), or fix forward on `main` and let the next Release PR cut a new version. Never move or reuse a tag.
- **A tag exists but was never published.** A valid resting state. Re-run publish, or abandon the version and let the next release take the following number.
- **Release PR stopped appearing.** First check that `RELEASE_PLEASE_TOKEN` has not expired. Then check for a stale `autorelease: pending` label on an already-merged Release PR — Release Please treats that as a release still in flight and will not open another. This failure is silent: the workflow still reports success.
- **Break-glass (automation unavailable).** Bump `__version__`, match `.release-please-manifest.json`, commit, tag, and push. The tag starts the same gated workflow — never bypass it.

### Post-release verification

**Verify the release against the dogfood cookbook.**

Once **Publish to PyPI** succeeds, confirm the downstream consumer still passes on the freshly published version:
- In [`azure-functions-cookbook-python`](https://github.com/yeongseon/azure-functions-cookbook-python), upgrade to the new release (`hatch run pip install -U "azure-functions-doctor>=X.Y,<1"`) and run `make test`.
- Treat any new `RuntimeWarning`/`DeprecationWarning` surfaced by this library during the cookbook run as a release-blocking signal — decorator-order and API-drift problems are reported as warnings, so a clean run (zero warnings from this package) is part of the release gate.
- If the cookbook pins a lower bound (`azure-functions-doctor>=X.Y,<1`), bump it to the new minor in the same verification PR so examples are tested against the version they advertise.
- A release is **not** considered done until the cookbook passes on the published version.

## Golden Commands

Use Makefile entry points only. Do not bypass the Makefile in CI or contributor guidance.

| Purpose | Command |
| --- | --- |
| Environment setup | `make install` |
| Format code | `make format` |
| Check formatting (`src`, `tests`) | `make format-check` |
| Lint | `make lint` |
| Type check | `make typecheck` |
| Tests | `make test` |
| Coverage | `make cov` |
| Full validation | `make check-all` |
| Docs build | `make docs` |
| Package build | `make build` |

## Compatibility Rules

- Runtime code must remain compatible with Python `3.10`.
- Public APIs must be fully typed.
- Avoid silent behavior changes.
- Breaking changes require explicit documentation and versioning discussion.

## Testing Rules

- Public APIs require tests.
- Bug fixes require regression tests.
- Representative and complex examples must remain smoke-tested.
- `make check-all` is the minimum merge gate.

## Commit Rules

Titles for issues, pull requests, and commits follow the **Title Convention** in [`CONTRIBUTING.md`](CONTRIBUTING.md#title-convention), the single source of truth for the format and the allowed types.

## Agent Rules

When using AI-assisted development:

- Prefer small, reviewable changes.
- Do not guess about behavior that can be verified.
- Keep repository structure aligned with sibling repositories.
- Update docs, examples, and tests together when behavior changes.

## Final Rule

If it is not automated, it will drift.
If it is not documented, it is not a stable rule.

## Merge Policy

- `main` requires a pull request, every required status check green, and all conversations resolved. It requires **zero approving reviews**: `yeongseon` is the only account with push access and GitHub forbids approving your own PR, so a required approval could only ever be met by an administrator bypass. The required checks are what guard `main`.
- **Never use `gh pr merge --admin` to skip a failing or pending required check.**
- Review is still expected, just not enforced. An AI review (`COMMENTED`) is not an approval.
- **Dependabot:** `pip` patch/minor updates auto-merge on green CI. `github-actions` updates never auto-merge — confirm each pinned SHA matches its claimed tag (`git ls-remote --tags <repo>`, compare against the dereferenced `^{}` commit) before merging. `dependabot-automerge.yml` enforces the split on all three of its auto-merge paths (security fast path, 3-day maturity, scheduled sweep).
- If a second maintainer ever gets push access, raise the approval count back to 1.

## Branch Hygiene

- Merged PR branches are deleted automatically ("Automatically delete head branches" is enabled on this repository); keep that setting on.
- When merging from the CLI, always pass `--delete-branch` (e.g. `gh pr merge --squash --delete-branch`) so the head branch is removed.
- Never delete `main` or `gh-pages`, and never delete a branch that still has an open PR.
- Run `git fetch -p` periodically to prune stale local tracking refs.
