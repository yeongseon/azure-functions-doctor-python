# Positioning: how this compares to the official `azure-functions-skills` doctor

**Use this when you need offline, deterministic, source-linked Python compatibility checks before deploy (no AI/cloud dependency required).**

Microsoft ships an official `doctor` skill inside
[`Azure/azure-functions-skills`](https://github.com/Azure/azure-functions-skills),
a coding-agent plugin for GitHub Copilot, Claude Code, and Codex. It shares the
`doctor` name with this package, so this page explains what each tool is for and
how they fit together.

## TL;DR

- **`azure-functions-doctor` (this package)** — a PyPI-installed CLI that runs
  **offline** and **deterministically**. It has no LLM, no cloud calls, and no
  network dependency. Every finding maps to a source-linked rule in an auditable
  catalog, and it goes deep on **Python v2** runtime, hosting-plan, and deploy
  compatibility. It is safe to run unattended in CI and on pull-request
  workspaces.
- **The official `azure-functions-skills` doctor** — a multi-language
  **coding-agent skill** whose headline value is **LLM semantic analysis**. Its
  `--deep` mode runs an AI agent (with elevated file-write / shell-exec
  permissions) to catch semantic issues that deterministic rules cannot.

These are complementary. You can run this package as a fast, deterministic
pre-deploy gate and use the official skill's AI analysis for semantic review
inside your coding agent.

## Comparison

| Dimension | `azure-functions-doctor` (this package) | `azure-functions-skills` doctor (official) |
| --- | --- | --- |
| **Primary form** | PyPI Python package + official GitHub Action | Coding-agent plugin (skills + Azure MCP), distributed via npm `@azure/functions-skills` and plugin marketplaces |
| **Core engine** | Deterministic rule catalog — **no LLM required** | LLM semantic analysis is the headline value (`--deep`); a `--no-deep` Tier-1 deterministic mode also exists |
| **Offline / CI-safe** | Yes — fully offline, no network or cloud, safe to run on PR workspaces | Deep mode needs an AI agent with elevated permissions and **refuses to run on PR workspaces** (prompt-injection risk); `--no-deep` is the CI-safe tier |
| **Transparency / auditability** | Every finding cites a rule in a source-linked catalog; output is reproducible | Deep findings come from LLM reasoning; `--no-deep` is deterministic |
| **Language focus** | **Python v2** decorator model — deep runtime/hosting-plan/deploy checks (Python lifecycle, hosting-plan Python caps, Flex config, binding connection resolution) | Multi-language, not Python-specific |
| **Runtime required** | Python 3.10+ | Node.js 20+ (Node 24+ for Copilot CLI) |
| **Determinism** | Deterministic — same inputs produce the same findings | Deep mode is non-deterministic; `--no-deep` is deterministic |

## Naming relationship

This project is an **independent community package** published on PyPI as
`azure-functions-doctor`. It is **not affiliated with, endorsed by, or
maintained by Microsoft**. The official skill lives at
`templates/skills/azure-functions-doctor` inside `Azure/azure-functions-skills`
and happens to share the `doctor` name because both diagnose Azure Functions
projects.

To disambiguate:

- **This package** is what you `pip install azure-functions-doctor` and invoke as
  `azure-functions-doctor doctor`.
- **The official skill** is what you add to a coding agent via the
  `azure-functions-skills` plugin.

## When to use which

- **Reach for this package** when you want a fast, offline, deterministic gate
  that runs the same way locally, in CI, and on pull requests — with every
  finding traceable to a documented rule, focused on Python v2 deploy
  compatibility.
- **Reach for the official skill** when you want AI-assisted semantic review
  (missing error handling, blocking I/O, hardcoded secrets, durable-orchestrator
  non-determinism) from inside your coding agent, and you can grant it a trusted
  workspace.

They are not mutually exclusive — running both gives you deterministic
pre-deploy coverage plus AI-assisted semantic analysis.
