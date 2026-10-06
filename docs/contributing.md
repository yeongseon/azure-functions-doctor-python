# Contributing to Azure Functions Doctor

This guide provides instructions for contributing to Azure Functions Doctor. Follow these standards to ensure a smooth review process and maintain code quality.

## Getting Started

1. Fork the repository on GitHub and clone your fork locally.
2. Add the upstream remote to stay synced with the main repository:
   ```bash
   git remote add upstream https://github.com/yeongseonchoe/azure-functions-doctor.git
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

All contributions must adhere to the following tools and configurations:

- **black (26.3.0)**: Used for code formatting. Line length is set to 100. Targets Python 3.11 through 3.14.
- **ruff (v0.15.5)**: Used for linting. We select E, F, and I rules. Line length is set to 100.
- **mypy (v1.19.1)**: Used for static type checking. We use strict mode, ignore missing imports, and exclude the `examples/` directory.
- **bandit (1.9.4)**: Used for security scanning of the `src/` directory.
- **forbid-korean**: A pre-commit hook ensuring all code and documentation are written in English.

### Makefile Targets

Use these commands to manage your development environment:

| Target | Description |
|--------|-------------|
| make format | Format code with ruff and black |
| make lint | Run style checks using ruff |
| make typecheck | Run mypy in strict mode |
| make test | Run the full test suite |
| make cov | Run tests and generate a coverage report |
| make security | Run bandit security scans |
| make check-all | Run all formatting, linting, type checking, and tests |

## Adding New Diagnostic Rules

To add a new diagnostic rule to the doctor:

1. Define the rule metadata in `src/azure_functions_doctor/assets/rules/v2.json`.
2. Implement the logic for the rule as a handler method in `src/azure_functions_doctor/handlers/registry.py`.
3. Register the handler type in the `_RULE_DISPATCH` map (`src/azure_functions_doctor/handlers/_helpers.py`).
4. Add unit tests for the new handler in `tests/test_handler.py`.
5. Update any relevant documentation if the behavior changes user expectations.

### Handler Guidelines

- Always return a dictionary with `status` and `detail` keys.
- Use the internal `_create_result()` helper for consistent response structures.
- Use `_handle_exception()` to manage unexpected errors gracefully.
- Include appropriate logging with `logger.debug()` or `logger.warning()`.
- Ensure each handler stays focused on a single responsibility.

## Testing Requirements

- Every new handler and CLI change must include tests.
- Use `tmp_path` for tests that interact with the filesystem.
- Use `CliRunner` from Click for testing CLI interactions and outputs.
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
