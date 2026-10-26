# Agent Playbook

## Source Of Truth
- [AGENTS.md](https://github.com/yeongseon/azure-functions-doctor-python/blob/main/AGENTS.md) for repository scope, issue conventions, and automation rules.
- [docs/review-evidence-policy.md](review-evidence-policy.md) for additional review evidence on high-risk changes (advisory, not server-enforced).
- `README.md` for architecture, usage, and exit-code expectations.
- `CONTRIBUTING.md` for diagnostic rule guidelines and contribution workflow.
- `pyproject.toml` and `Makefile` for supported commands and environments.

## Repository Map
- `src/azure_functions_doctor/` CLI and diagnostic logic.
- `tests/` regression coverage for rules and CLI behavior.
- `docs/` published documentation assets.

## Change Workflow
1. Read the existing diagnostic flow before changing rule behavior.
2. Keep command-line behavior stable unless the change explicitly updates the contract.
3. Add or update tests for every new rule, warning, or exit-path change.
4. Update `README.md` when usage examples, dependencies, or output semantics change.

## Pull Request Descriptions

Follow `AGENTS.md` for concise PR titles, changes and actual validation.
Include additional review evidence for significant findings or high-risk changes under
[review-evidence-policy.md](review-evidence-policy.md). Diagnostic rule, detection,
and configuration changes also retain the representative-project validation record
defined there, even when routine: profile, target runtime, configuration/suppression,
expected statuses and exit result, display severity, required default, and any
explicit gate override.

## Validation
- `make install`
- `make test`
- `make lint`
- `make typecheck`
- `make build`
