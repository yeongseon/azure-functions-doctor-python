# Contributing Guide

We welcome contributions to the `azure-functions-doctor` project.

## Branch Strategy

Use GitHub Flow and branch from `main`.

Recommended branch prefixes:

- `feat/` for new features
- `fix/` for bug fixes
- `docs/` for documentation-only changes
- `chore/` for tooling and maintenance
- `ci/` for workflow updates

## Development Workflow

1. Create a branch from `main`.
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature-name
   ```
2. Write code and tests.
3. Run the local quality gate.
   ```bash
   make check-all
   ```
4. Push and create a pull request.
   ```bash
   git push origin feat/your-feature-name
   ```

## Local development quickstart

Local development requires Python 3.11 and GNU Make because Hatch creates its
default development environment with Python 3.11. The published package
supports Python 3.11, 3.12, 3.13, and 3.14. No Azure subscription, Azure
Functions Core Tools, Azurite, or Docker is required for `make check` or
`make test`. Full local verification requires Core Tools (`func`) and Azurite.

Install Hatch once in an isolated tool environment, then create the project
development environment:

```bash
make install
```

Then run the standard verification commands:

```bash
make test
make check
make verify
```

Local commands use Hatch's Python 3.11 environment. Routine targets never upgrade
pip or reinstall Hatch. `make bootstrap` only checks Hatch availability;
`make install-ci` installs into CI's explicitly selected `PYTHON` without Hatch.

## Project Commands

| Command | Contract |
| --- | --- |
| `make install` | Create Hatch dev/docs environment and local hooks |
| `make install-ci` | Install dev/docs extras into CI's selected interpreter |
| `make doctor` | Read-only developer prerequisites; nonzero when required tools are missing |
| `make format` / `make format-check` | Mutating Ruff formatting / non-mutating check |
| `make check` | Ruff lint/format, strict mypy once, Bandit, workflow and lightweight docs policy |
| `make test` | Offline regression suite including every diagnostic-rule test; coverage >=95% |
| `make integration` | Static example CLI plus managed real Functions host and private Azurite |
| `make verify` | Check + test + integration + installed-wheel CLI smoke + build + strict docs |
| `make e2e-azure` | Explicitly configured deployed Azure URL and candidate identity; no provisioning |
| `make report` | Render saved evidence only; never rerun checks |
| `make clean` | Remove generated artifacts only; preserve environments and external data |

`make check-all` is an exact backward-compatible alias of `make verify`.
`make clean-all` retains historical deep cleanup, including `.venv` and bytecode.
`lint`, `style`, `typecheck`, `security`, `cov`, `lint-workflows`, `cli-smoke`,
`host-smoke`, `wheel-smoke`, `build`, and `docs` are focused/partial targets.
`e2e-local` checks an already-running local app, not Azure certification.

### Two different doctors

`make doctor` checks this repository's **developer environment** without installing
anything. It requires Python >=3.11, Hatch or an active venv, Ruff, mypy, pytest and
Bandit. It reports `func`/Azurite as required only for host-smoke/integration/verify,
and reports optional tooling separately. No Chrome, mermaid-cli or Docker is
required by `check`; the existing structural Mermaid linter remains lightweight.

`azure-functions-doctor doctor --path <app>` is the **product CLI**, which diagnoses
an Azure Functions project. Its rule skips/optional findings are not pytest skips.
CLI regression tests and the static/installed-wheel smoke lanes exercise it
independently of the developer prerequisite checker.

### Evidence and certification

Generated, gitignored `test-results/` contains separate `test/`, `cli-smoke/`,
`wheel-smoke/`, `host-smoke/`, `integration/`, `build/`, `docs/`, `verify/` and
`azure-e2e/` lanes. Summaries include schema version, command, counts, status,
exit code and supporting paths. Offline tests save JUnit and coverage XML;
integration saves `junit/` and redacted logs; every lane saves environment metadata.
Console and GitHub Job Summary render the same saved counts. CI uploads evidence
with `if: always()`. Credentials, connection strings, headers, SAS and tokens are
masked in verification evidence; this does not change product CLI output policy.

PASS requires executed checks. Missing prerequisites/results, zero tests, all-skipped
or any unexpected required skip are INCOMPLETE/nonzero. Failed assertions/processes
are FAIL. Action integration, published `@v1` consumers and cookbook soak remain
in their existing workflows and are NOT_APPLICABLE locally, never inferred PASS.

The host runner owns temporary app/storage directories, unique loopback ports and
process groups, and cleans only those resources on completion, timeout or signals.
Wheel smoke builds a fresh candidate, records its SHA-256/version, installs it into
an isolated temporary venv outside the checkout and executes the installed CLI.
It reuses the selected environment's dependencies through a `.pth` for offline
installation; the package import is asserted to come from the candidate wheel.

`make e2e-azure` requires a deployed HTTPS `E2E_BASE_URL` (not localhost/private IP)
and `E2E_EXPECTED_VERSION` matching the installed diagnostic CLI. It preflights
before pytest and requires both existing remote-suite assertions to execute.
These tests prove deployed HTTP plus local CLI diagnostics, **not a deployed doctor
version endpoint**: `deployed_version_match` is NOT_APPLICABLE. Candidate version,
installed-wheel identity and live-host execution remain distinct evidence.
Release certification retains its existing ref/version record, OIDC, gates and
exact-artifact upload; local verification never certifies Azure.

Before opening a PR, run `ruff format --check <changed-python-files>` (or
`ruff format <changed-python-files>` to fix them). `make format-check` checks
`src`, `tests` and the verification tool modules without changing files. CI checks those trees and also
reports formatting failures on changed Python files in a dedicated step.

## GitHub Actions Pinning

All external `uses:` references in `.github/workflows/` MUST pin to a
full 40-character commit SHA with a trailing comment documenting the
released version or channel. Example:

```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
```

This applies to first-party (`actions/*`, `github/*`, `azure/*`) and
third-party Actions alike.

**Rationale.** Mutable tags (including immutable-looking version tags
like `@v6.0.1`) can be retroactively moved by an attacker who gains
write access to the upstream repository. The
[`tj-actions/changed-files` compromise (CVE-2025-30066, March 2025)](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction)
demonstrated this exact failure mode: ~23,000 repositories had their CI
secrets exfiltrated, and only workflows that pinned to a commit SHA were
safe. GitHub's own guidance now identifies SHA pinning as
[the only way to use an Action as an immutable release](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#using-third-party-actions),
and OpenSSF Scorecard's
[`Pinned-Dependencies` check](https://github.com/ossf/scorecard/blob/main/docs/checks.md#pinned-dependencies)
flags anything weaker as Medium-risk.

Dependabot updates SHA-pinned references on the configured schedule and
keeps the trailing version comment in sync, so the human-readable
context never drifts from the pinned commit.

**Approved exceptions.** The following mutable refs are the only ones
permitted in this repository and are flagged with an inline comment at
the call site:

- Local composite actions (`uses: ./...`) — versioned with the repo.

When adding a new external Action, resolve the SHA with
`git ls-remote <repo-url> 'refs/tags/<tag>^{}'`. The trailing `^{}`
**dereferences** the ref to its target commit; without it, an
*annotated* tag returns the tag-object SHA instead of the commit SHA,
and the tag-object SHA is **not** a valid `uses:` target.

```bash
# Annotated tag — the two forms return *different* SHAs:
git ls-remote https://github.com/Azure/login 'refs/tags/v3.0.0' 'refs/tags/v3.0.0^{}'
# 93381592...   refs/tags/v3.0.0       <- tag object, do NOT pin to this
# 532459ea...   refs/tags/v3.0.0^{}    <- commit, pin to this one

# Lightweight tag — only the non-deref form returns a row, and it is
# already the commit SHA. Always include the `^{}` form anyway so the
# same command works for both tag types:
git ls-remote https://github.com/actions/setup-python 'refs/tags/v6' 'refs/tags/v6^{}'
```

Single-quote the `refs/...^{}` argument so the `{}` and `^` are not
interpreted by your shell (notably zsh with `EXTENDED_GLOB`).

## Example Coverage Policy

Examples are part of the supported API experience and should stay verified.

- Keep one representative example for the minimal diagnostic check workflow.
- Keep one complex example for custom checks and environment-specific diagnostics.
- Add or update smoke tests whenever an example changes.
- Prefer lightweight smoke coverage over infrastructure-heavy end-to-end tests.

## Issue Scope

When opening or editing an issue, follow the
[Issue Conventions in AGENTS.md](AGENTS.md#issue-conventions), including the
repository-scope checks. Describe this repository's problem and acceptance
criteria, and explain why any external repository reference is relevant.

## Title Convention

This section is the single source of truth for issue, pull request, and commit titles in this repository. `AGENTS.md`, the pull request template, the issue forms, and the documentation site point here instead of restating the rules.

Issues, pull requests, and the final squash commit on the default branch all use:

```text
type: description
type(scope): description
```

- Write titles in English.
- `type` and `scope` are lowercase. Put exactly one space after the colon.
- `scope` is optional. Add it only when it narrows the area; do not add one just for uniformity.
- `description` states what changes and why, concisely. Start with a lowercase word, but keep the spelling of API names, acronyms, error codes, and proper nouns.
- No trailing period.
- No priority, size, status, or owner markers, and no bracket prefixes such as `[Bug]`, `[Feature]`, or `[WIP]`. Use labels and Draft pull requests instead.
- An issue title may describe the problem; the pull request title describes the change that resolves it. Keep them aligned when they cover the same work, without forcing identical wording when the scope differs.
- Do not put issue numbers in pull request titles. Link issues in the pull request body with `Closes #123` or `Refs #123`.

| type | use for |
|---|---|
| `feat` | a user-facing feature or capability |
| `fix` | a bug fix in product behavior |
| `docs` | documentation only |
| `test` | adding or changing tests |
| `perf` | a performance improvement |
| `refactor` | internal restructuring that keeps external behavior |
| `ci` | CI and automation workflows |
| `build` | build, packaging, and dependency changes |
| `chore` | maintenance that fits none of the above |
| `style` | formatting only, no behavior change |
| `revert` | reverting an earlier change |

A breaking change adds `!` before the colon: `type!: description` or `type(scope)!: description`. Whether a change is breaking, and how it is released, is decided by the Release Process in [AGENTS.md](AGENTS.md), not by the title alone. Release Please reads these titles from the squash commits on `main`: `fix` and `feat` drive the version bump, and the other types only shape the changelog.

Examples:

```text
fix: report invalid host.json without a traceback
feat(cli): add a JSON output option
docs(readme): clarify the local setup steps
refactor!: rename the public configuration keys
```

Not accepted: `[Bug] crash on save` (bracket prefix, no type), `Fix: crash on save` (uppercase type), `feature: add export` (type not in the table), `fix: crash on save.` (trailing period), `fix: report invalid host.json without a traceback (#503)` (the pull request number belongs in the body).

Pull requests are squash-merged and the pull request title becomes the final commit title. GitHub appends the pull request number by itself, so `fix: report invalid host.json without a traceback` lands on `main` as `fix: report invalid host.json without a traceback (#503)`. Do not write that number into the title yourself — the check rejects a title ending in `(#123)`, because it would be doubled. Link the issue from the pull request body instead, for example `Closes #503`. The **PR title** check validates the format whenever a pull request is opened, edited, reopened, or updated. Individual commits on a branch are not checked.

Issue titles are not enforced. Anyone can open an issue without knowing this convention; maintainers adjust the title during triage.

## Releases

Merging to `main` does not publish a release.

Release Please keeps an open **Release PR** showing what the next version would
be; merging that PR is what cuts the release, and it is what creates the `v*`
tag that starts the publish workflow. Publishing happens only after the release
verification requirements have been satisfied. Contributors never need to bump a
version or tag anything in an ordinary pull request.


See `AGENTS.md` for the maintainer-only release procedure.

## Code of Conduct

Be respectful and inclusive. See our [Code of Conduct](CODE_OF_CONDUCT.md) for details.
