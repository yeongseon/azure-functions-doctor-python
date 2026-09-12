# PRD - azure-functions-doctor

## Overview

`azure-functions-doctor` is an **Azure Functions Python runtime & deployment diagnostic engine**.
It answers one question with an auditable, deterministic verdict:

> **Will _this exact_ Python app run on _this exact_ Azure Functions configuration?**

It inspects a local project — source, dependencies, `host.json`, and (when present) the
deployment/runtime configuration — and reports compatibility and configuration problems
**before** they surface as cold-start failures, host errors, or deployment rejections.

## Problem Statement

Deploying an Azure Functions app is expensive to get wrong: the worker starts, the host reads
config, and only then does an incompatibility surface — in a production log. The failure classes
that slip through generic checks are specifically about **runtime and hosting compatibility**:

- a Python version the target **hosting plan** does not support (e.g. Python 3.14 on Linux
  Consumption, which is capped at 3.12)
- a Python version approaching or past its **Azure Functions end-of-support** date
- an end-of-life **Functions runtime** (v1.x, or v3.x on Linux Consumption) still pinned via
  `FUNCTIONS_EXTENSION_VERSION`
- Flex Consumption misconfiguration (deprecated app settings, missing deployment storage,
  runtime declared in `functionAppConfig.runtime` rather than app settings)
- bindings whose connection settings are not actually resolvable in the deployed configuration

These are discovered late, through confusing runtime errors or deployment issues. The tool moves
that failure **left** — catch it locally or in CI, not in production.

## Goals

- Provide a fast, readable, **deterministic** compatibility verdict for Azure Functions Python
  projects against a specific target runtime and hosting plan.
- Ground every date/compatibility finding in a **version-controlled, source-linked catalog** —
  no invented dates, no runtime network calls.
- Surface required and optional checks with clear pass/fail output and actionable remediation.
- Support both local CLI use and CI integration (table, JSON, SARIF, JUnit).
- Keep checks aligned with representative example projects.

## Non-Goals

- **Fixing** project issues automatically (it diagnoses; it does not mutate the project).
- Replacing Azure Functions Core Tools or managing deployment workflows.
- Supporting the legacy `function.json`-based Python **v1** model.
- **Multi-language** support — this engine is deliberately Python-specific.
- **Generic semantic linting** or style checks (use `ruff`/`mypy`).
- **Generic security scanning** (use dedicated SAST/dependency scanners).
- **Runtime network calls** of any kind — the compatibility core is fully offline and auditable.
- Letting an **AI agent infer compatibility**. Compatibility is decided only by the deterministic
  core against the source-linked catalog; an agent must never guess a date or a support matrix.

## Architecture

```
deterministic core (offline, auditable)  ->  findings  ->  optional future agent layer
        │                                        │                     │
   source-linked catalog                  evidence + source +    consumes findings only;
   (no AI, no cloud, no network)          freshness per finding  NEVER infers compatibility
```

- **Deterministic core.** All compatibility decisions come from a version-controlled catalog of
  Azure Functions facts (Python lifecycle, hosting-plan Python caps, runtime lifecycle). Every
  fact carries a source URL, a `last_verified` date, and precision-tagged lifecycle dates, so the
  tool never renders finer precision than Microsoft publishes. The core has **no AI and no cloud
  dependency**.
- **Findings.** Each finding carries its evidence, the source it was derived from, and the
  freshness of the underlying catalog snapshot (a stale catalog reports its own signal, separate
  from any finding severity).
- **Optional future agent layer.** A later agent may *consume* findings to explain or prioritize
  them, but it must **never** infer compatibility, synthesize dates, or override the core verdict.

### The moat

`azure-functions-doctor` is **auditable, deterministic, offline, source-linked, and
Python-specific**. Every verdict can be traced to a cited Microsoft source, reproduced without
network access, and reviewed in version control.

## Primary Users

- Maintainers of Azure Functions Python repositories
- Developers preparing an app for deployment to a specific Azure Functions plan
- Teams that want a lightweight, deterministic CI gate before deploying Functions projects

## Core Use Cases

- Run diagnostics against the current project directory
- Run diagnostics against a specific example or target path
- Pin the target runtime explicitly (`--target-python`) when the tool's interpreter differs from
  the deployed Python version
- Use a smaller profile for required-only checks
- Consume human-readable or machine-readable output (table / JSON / SARIF / JUnit) in automation

## Success Criteria

- Representative examples pass diagnostic smoke tests in CI
- Broken example copies fail in predictable, source-attributable ways
- Every date/compatibility finding is traceable to a cited source in the catalog
- CLI output remains stable enough for user troubleshooting and automation

## Example-First Design

### Philosophy

A diagnostic CLI earns trust by showing exactly what it does — and, crucially, **why**.
`azure-functions-doctor` ships runnable example projects — both healthy and intentionally broken —
so developers can see real pass/fail output, with cited reasons, before pointing the tool at their
own code.

### Quick Start (Hello World)

Run diagnostics against the representative example:

```bash
pip install azure-functions-doctor
azure-functions-doctor doctor --path examples/v2/http-trigger
```

Expected output shows a clean diagnostic pass:

```text
Azure Functions Doctor
Path: examples/v2/http-trigger

  [✓] host.json: host.json exists
  [✓] requirements.txt: requirements.txt exists
  [✓] azure-functions package: declared in requirements.txt
  [✓] Programming model v2: decorators found
  ...

Doctor summary (to see all details, run azure-functions-doctor doctor -v):
  0 fails, 0 warnings, N passed
Exit code: 0
```

Run against a broken example to see clear failure output:

```bash
azure-functions-doctor doctor --path examples/v2/broken-missing-host-json
```

### Why Examples Matter

1. **Lower entry barrier.** Developers can run the CLI against bundled examples before
   applying it to their own project. The pass/fail contrast builds confidence.
2. **AI agent discoverability.** Tools like GitHub Copilot, Cursor, and Claude Code recommend
   libraries based on README, PRD, and example content. CLI output samples in documentation
   help AI agents understand what `azure-functions-doctor` does and when to suggest it —
   while the compatibility verdict itself stays in the deterministic core, never the agent.
3. **Cookbook role.** For niche ecosystems, `examples/` and `docs/` often serve as the primary
   learning material. Both healthy and broken examples teach diagnostic patterns.
4. **Proven approach.** FastAPI, LangChain, SQLAlchemy, and Pandas all achieved early adoption
   through extensive, copy-paste-friendly examples and clear output samples.

### Examples Inventory

| Role | Path | Pattern |
|---|---|---|
| Representative | `examples/v2/http-trigger` | Minimal HTTP trigger (passes all checks) |
| Representative | `examples/v2/timer-trigger` | Timer trigger (passes all checks) |
| Complex | `examples/v2/multi-trigger` | Multiple triggers in one app |
| Complex | `examples/v2/blueprint` | Blueprint-based modular routing |
| Broken | `examples/v2/broken-missing-host-json` | Missing host.json |
| Broken | `examples/v2/broken-missing-requirements` | Missing requirements.txt |
| Broken | `examples/v2/broken-missing-azure-functions` | Missing azure-functions dep |
| Broken | `examples/v2/broken-no-v2-decorators` | No v2 decorators |

All examples are smoke-tested in CI. New diagnostic rules should ship with a corresponding
broken example that demonstrates the failure.
