# Architecture

This document explains how `azure-functions-doctor` is structured internally and why key design choices support deterministic, actionable diagnostics.

## Design Objectives

The package is intentionally focused:

- Keep diagnostics rule-driven and data-defined (JSON rule assets, not hardcoded checks).
- Preserve exit-code-based CI integration as a first-class concern.
- Add invocation context without requiring heavy runtime dependencies.
- Stay dependency-light and operationally predictable.

## High-Level Components

Core modules and responsibilities:

- `__init__.py`: public exports and version string.
- `cli.py`: Typer-based CLI entrypoint; maps flags to `Doctor` options.
- `doctor.py`: `Doctor` runner — loads rules, executes handlers, aggregates results.
- `handlers/` package: `Rule` type and shared helpers (`_helpers.py`), plus `generic_handler` and type-based rule dispatch via `HandlerRegistry` (`registry.py`) over per-domain implementation modules (`generic`, `dependencies`, `runtime`, `monitoring`, `deployment`, `bindings`, `project`, `durable`, `integrations`).
- `config.py`: configuration management (reserved for future use; not yet in the runtime path).
- `target_resolver.py`: resolves runtime values (Python version, Core Tools version) for version-comparison checks.
- `logging_config.py`: internal logging setup.
- `schemas/`: JSON schema definitions for rule assets.
- `assets/`: built-in rule inventory (e.g. `rules/v2.json`).

## Public API Boundary

Public symbols intentionally kept small:

- `Doctor`
- `__version__`
- `run_diagnostics()` (from `api.py` — programmatic entrypoint)

CLI is the primary consumer. Python import use is for programmatic embedding only.

## Module Boundaries

```mermaid
flowchart TD
    CLI["cli.py<br/>Typer CLI"]
    DOC["doctor.py<br/>Doctor runner"]
    HDLR["handlers/<br/>Rule dispatch + generic_handler"]
    TR["target_resolver.py<br/>Version resolution"]
    RULES[("assets/<br/>Rule inventory")]
    SCHEMAS[("schemas/<br/>JSON schemas")]
    LOG["logging_config.py<br/>Internal logging"]

    CLI --> DOC
    DOC --> HDLR
    DOC --> RULES
    DOC --> SCHEMAS
    HDLR --> TR
    CLI --> LOG
    DOC --> LOG
```

## Diagnostic Pipeline

`Doctor.run_all_checks()` is the entrypoint for a full diagnostic scan.

Execution flow:

1. Load rule asset (`assets/rules/v2.json`) or custom `rules_path`.
2. Validate rule asset against JSON schema.
3. Apply profile filter if `--profile` is given.
4. Dispatch each rule to its handler by the rule's `type` field.
5. Aggregate `SectionResult` list with per-item `CheckResult` entries.
6. Return `list[SectionResult]` — overall pass/fail status is derived later by the CLI.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as cli.py
    participant DOC as Doctor
    participant RULES as assets/v2.json
    participant HDLR as handlers/
    participant TR as target_resolver.py

    Dev->>CLI: azure-functions-doctor doctor --path ./my-project
    CLI->>DOC: Doctor(path, profile, rules_path)
    DOC->>RULES: load + schema-validate rules
    DOC->>DOC: apply profile filter
    loop each rule
        DOC->>HDLR: dispatch rule by type
        HDLR->>TR: resolve version targets (if needed)
        TR-->>HDLR: resolved value
        HDLR-->>DOC: CheckResult
    end
    DOC-->>CLI: list[SectionResult]
    CLI-->>Dev: formatted output (table/json/sarif/junit)
```

## Rule Asset Design

Rules are data, not code:

- Each rule is a JSON object with `id`, `category`, `label`, `type`, `condition`, and optional `hint`.
- Handlers dispatch on the rule's `type` field and evaluate `condition` against the target project.
- New checks can be added without touching Python logic.

See [Rule Inventory](rule_inventory.md) and [RULE_POLICY](RULE_POLICY.md) for the full rule catalogue.

## Exit Code Contract

The CLI follows a strict exit code contract:

| Exit code | Meaning |
|---|---|
| `0` | No checks failed |
| `1` | One or more checks failed |
| `2` | Usage error (bad arguments) |

CI pipelines can rely on these codes directly. See [JSON Output Contract](json_output_contract.md) for structured output.

## Profile System

Profiles allow subsets of rules:

- Profile is a string selector, not a file-based system. Four profiles are accepted: `minimal` (only rules with `required=True`), `deploy` (core-group rules minus dev-environment checks — runtime/hosting/deployment correctness), `development` (dev-environment checks: venv, Python executable, Core Tools, local.settings), and `full` (default when omitted: all rules).
- Membership is computed in `azure_functions_doctor.profiles` from rule metadata (single source of truth shared with the generated rule inventory).
- Custom profile names raise `ValueError`; only the four names above are accepted.

See [Configuration](configuration.md) and [Minimal Profile](minimal_profile.md).

## Key Design Decisions

### 1. JSON rule assets over hardcoded checks

Every diagnostic check is defined as a JSON object in the rule inventory (`assets/rules/v2.json`). New checks are added by appending rule data — no Python handler changes required unless a new rule `type` is introduced.

### 2. HandlerRegistry type-based dispatch

The `handlers/` package (`registry.py`) maintains a `HandlerRegistry` that maps rule `type` strings to handler functions. The `Doctor` runner dispatches each rule to its handler by type, enabling extensibility without modifying dispatch logic.

### 3. Exit code contract

`cli.py` sets exit code 1 explicitly when any check fails. Exit code 0 results from explicit `typer.Exit(0)` in structured-output paths and normal return in table mode. Exit code 2 is not explicitly coded — it is the default behaviour of Typer/Click when invoked with invalid arguments.

### 4. String-based profile selection

Profiles are not file-based. The `--profile` flag accepts `minimal`, `deploy`, `development`, or `full` (default when the flag is omitted: all rules). Membership is computed from rule metadata in `azure_functions_doctor.profiles` (`Doctor.run_all_checks()` filters with it). This avoids external profile file management while covering the common cases: gating CI on required rules (`minimal`) or on deployment correctness (`deploy`).

### 5. Typer CLI framework

The CLI uses Typer for argument parsing, help generation, and shell completion. This was chosen over argparse/Click for its decorator-driven API and automatic type inference from Python type hints.

## Related Documents

- [Usage Guide](usage.md)
- [Configuration](configuration.md)
- [Rules](rules.md)
- [Diagnostics](diagnostics.md)
- [Troubleshooting](troubleshooting.md)

## Sources

- [Azure Functions Python developer reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure Functions host.json reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-host-json)
- [Supported languages in Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages)

## See Also

- [azure-functions-validation — Architecture](https://github.com/yeongseon/azure-functions-validation) — Request/response validation and serialization
- [azure-functions-openapi — Architecture](https://github.com/yeongseon/azure-functions-openapi) — API documentation and spec generation
- [azure-functions-logging — Architecture](https://github.com/yeongseon/azure-functions-logging) — Structured logging with contextvars
- [azure-functions-scaffold — Architecture](https://github.com/yeongseon/azure-functions-scaffold) — Project scaffolding CLI
- [azure-functions-langgraph — Architecture](https://github.com/yeongseon/azure-functions-langgraph) — LangGraph runtime exposure for Azure Functions
