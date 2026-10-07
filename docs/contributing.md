# Contributing to Azure Functions Doctor

This guide provides instructions for contributing to Azure Functions Doctor. Follow these standards to ensure a smooth review process and maintain code quality.

## Getting Started

1. Fork the repository on GitHub and clone your fork locally.
2. Add the upstream remote to stay synced with the main repository:
   ```bash
   git remote add upstream https://github.com/yeongseon/azure-functions-doctor-python.git
   ```
3. Create and activate a virtual environment (using venv or your preferred tool).
4. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
5. Set up the pre-commit hooks:
   ```bash
   pre-commit install
   ```
6. Verify your setup by running the full quality gate:
   ```bash
   make check-all
   ```

## Development Workflow

1. Sync your local main branch with the upstream main branch.
2. Create a descriptive feature branch from main.
3. Implement your changes in the `src/azure_functions_doctor/` directory.
4. Add corresponding tests in the `tests/` directory.
5. Run `make check-all` to ensure all checks and tests pass locally.
6. Commit your changes using the Conventional Commits format.
7. Push your branch to your fork and create a Pull Request.

## Commit Message Convention

Titles for issues, pull requests, and commits follow the **Title Convention** in [`CONTRIBUTING.md`](https://github.com/yeongseon/azure-functions-doctor-python/blob/main/CONTRIBUTING.md#title-convention), the single source of truth for the format and the allowed types.

## Code Quality Standards

All contributions must adhere to the following tools. Exact pinned versions live
in `pyproject.toml` (`[project.optional-dependencies] dev`) and
`.pre-commit-config.yaml` — treat those files as the source of truth rather than
copying versions into docs:

- **ruff**: formatting and linting in one tool. Line length 100, target `py311`,
  rule selection `C4`, `E`, `F`, `I`, `UP`. There is no Black in this project;
  `ruff format` replaced it.
- **mypy**: static type checking in strict mode, with missing imports ignored
  and `tests/fixtures/` excluded.
- **bandit**: security scanning of `src/`.
- **forbid-korean**: a pre-commit hook ensuring code and documentation are
  written in English (locale READMEs excluded).

### Makefile Targets

Use these commands to manage your development environment:

| Target | Description |
|--------|-------------|
| make format | Format code with `ruff format` |
| make lint | Run `ruff` style checks and `mypy` |
| make typecheck | Run mypy in strict mode |
| make test | Run the full test suite |
| make cov | Run tests and generate a coverage report |
| make security | Run bandit security scans |
| make check-all | Run all formatting, linting, type checking, and tests |

## Adding New Diagnostic Rules

To add a new diagnostic rule to the doctor:

1. Define the rule metadata in `src/azure_functions_doctor/assets/rules/v2.json`.
2. Implement the logic for the rule as a handler method in `src/azure_functions_doctor/handlers/registry.py`.
3. Decorate that method with `@_rule_handler` (`src/azure_functions_doctor/handlers/_helpers.py`); it derives the rule type from the `_handle_` prefix and registers it in `_RULE_DISPATCH` automatically.
4. Extend `src/azure_functions_doctor/schemas/rules.schema.json` so the new type is schema-valid.
5. Add unit tests for the new handler in `tests/test_handler.py`.
6. Update any relevant documentation if the behavior changes user expectations.

### Handler Guidelines

- Always return a dictionary with `status` and `detail` keys.
- Use the internal `_create_result()` helper (`handlers/_helpers.py`) for consistent response structures.
- Use `_handle_exception()` to map unexpected errors onto a `fail` result instead of crashing the run.
- Include appropriate logging with `logger.debug()` or `logger.warning()`.
- Ensure each handler stays focused on a single responsibility.

## Testing Requirements

- Every new handler and CLI change must include tests.
- Use `tmp_path` for tests that interact with the filesystem.
- Use `CliRunner` from `typer.testing` for testing CLI interactions and outputs.
- Ensure you test all possible result statuses: `pass`, `warn`, `fail`, and `skip`.
- Mock external dependencies or network calls to keep tests fast and isolated.
- Use descriptive test names like `test_<handler>_returns_<status>_when_<condition>`.

## Example Coverage Policy

- Maintain at least one representative example for the smallest supported workflow.
- Include one complex example to demonstrate realistic integration scenarios.
- Add smoke tests whenever examples are modified.
- Prioritize lightweight smoke coverage over infrastructure-heavy end-to-end tests.

## Pull Request Process

1. Branch from the latest main branch.
2. Use the Conventional Commits format for your commit messages.
3. Include comprehensive tests for any new functionality.
4. Update documentation if your changes modify existing behavior.
5. Keep Pull Requests focused and atomic; avoid bundling unrelated changes.
6. Ensure all CI checks pass before requesting a review.
7. Link related issues in the description using keywords like `Fixes #123`.

## Code of Conduct

All contributors are expected to adhere to the standards outlined in our `CODE_OF_CONDUCT.md`.
