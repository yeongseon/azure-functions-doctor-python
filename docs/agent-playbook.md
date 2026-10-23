# Agent Playbook

## Source Of Truth
- [AGENTS.md](https://github.com/yeongseon/azure-functions-doctor-python/blob/main/AGENTS.md) for repository scope, issue conventions, and automation rules.
- [docs/review-evidence-policy.md](review-evidence-policy.md) for advisory review-evidence recording (not server-enforced; see AGENTS.md "Who approves what" for the actual required gate).
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

## Validation
- `make install`
- `make test`
- `make doctor` checks developer prerequisites, not product project diagnostics.
- `make check` runs complete non-mutating quality checks.
- `make integration` runs static CLI and managed real host/Azurite smoke.
- `make verify` is the full local gate; `make check-all` is its exact alias.
- `make e2e-azure` separately requires a deployed URL and expected candidate version.
- `make report` renders saved `test-results/` evidence without rerunning tests.
- `make clean` removes generated artifacts; `clean-all` also removes `.venv`.

The product `azure-functions-doctor doctor` remains independently tested. Missing
prerequisites or unexpectedly skipped required assertions never pass. See the
[Development Guide](development.md) for command and evidence boundaries.
