# Rule Policy for `azure-functions-doctor`

## Philosophy

`azure-functions-doctor` is designed as a **conservative static preflight checker**
for Azure Functions Python projects.

The goal is **not to enforce project style or preferences**, but to detect
**clear configuration problems** that are directly specified in official documentation.

The tool prioritizes:

- **Low false positive rate**
- **Deterministic checks**
- **Strong grounding in Microsoft Learn documentation**
- **Safe usage in CI pipelines**

> Prefer fewer rules with high confidence over many rules with uncertainty.

---

## Rule Classification Model

All built-in rules belong to one of three tiers.
The tier determines default severity (`required: true/false`) and lifecycle expectations.

### Tier 1 — Core Rules

Core rules represent **hard validation checks**.

They must satisfy **all** of the following:

- Directly required or explicitly specified in **Microsoft Learn documentation**
- Deterministic static check (file existence, package declaration, version comparison)
- Near-zero false positives across all valid project layouts
- Safe to fail CI builds — the fix is always unambiguous

Core rules are marked `"required": true` in `v2.json` and are always included in the
`--profile minimal` set. Adding or removing a core rule is a **semver-breaking change**.

#### Current Core Rules

| Rule ID | Check Type | MS Learn Reference |
|---|---|---|
| `check_python_version` | `compare_version` | [Supported Python versions][py-versions] |
| `check_requirements_txt` | `dependency_manifest` | [Managing dependencies][req-txt] |
| `check_azure_functions_library` | `package_declared` | [Python developer reference][az-func-lib] |
| `check_host_json` | `file_exists` | [host.json reference][host-json] |
| `check_host_json_version` | `host_json_version` | [host.json reference][host-json] |
| `check_durable_nondeterminism` | `durable_nondeterminism` | [Durable Functions code constraints][durable-determinism] |

These rules detect **unambiguous misconfiguration** — a project missing any of these
will fail to deploy or run regardless of environment.

> Note: `check_durable_nondeterminism` is also shipped as required (`"required": true`)
> because nondeterministic calls in orchestrator/entity functions reliably break Durable
> Functions replay. Unlike the other Core rules it relies on a specialized source detector
> (`durable_nondeterminism`) rather than a purely static file/version check, and it only
> evaluates projects that contain Durable orchestration or entity triggers.

---

### Tier 2 — Extended Rules

Extended rules are **officially recommended** configurations but not universally required.

These rules:

- May depend on local development environment (not deployment-time requirements)
- May be documented as "recommended" rather than "required" in Microsoft Learn
- Should produce **warnings** (`"required": false`), not hard failures
- Must not break CI builds unless explicitly opted-in via a custom rules file

Extended rules are included in `--profile full` but excluded from `--profile minimal`.

#### Current Extended Rules

| Rule ID | Reason for Extended (not Core) tier |
|---|---|
| `check_programming_model_v2` | Decorator detection uses AST heuristics; false positives possible in non-standard layouts |
| `check_blueprint_registration` | Blueprint registration is inferred from source; unusual registration patterns may be missed |
| `check_venv` | Recommended for local development; not a deployment-time requirement |
| `check_python_executable` | Interpreter path issues are environment-specific; not caused by project misconfiguration |
| `check_native_dependency_risk` | Heuristic package list; native builds may still succeed depending on the build environment |
| `check_azure_functions_worker` | Warns on a discouraged pin; not always fatal |
| `check_local_settings` | Local development convenience; not required for deployment |
| `check_funcignore` | Packaging hygiene recommendation; not required for deployment |
| `check_local_settings_git_tracked` | Secret-hygiene recommendation; depends on git state |
| `check_func_cli` | Core Tools useful locally; not required by Functions runtime |
| `check_func_core_tools_version` | Version guidance; not a runtime deployment requirement |
| `check_extension_bundle` | Binding support recommendation; not universally required |
| `check_extension_bundle_v4` | Version recommendation; not a hard requirement |
| `check_app_insights` | Observability recommendation; not required for app to run |
| `check_durabletask_config` | Conditional on Durable usage; heuristic detection |
| `check_asgi_wsgi_exposure` | Framework heuristic; non-standard callables may produce false positives |
| `check_decorator_order` | Decorator-stacking heuristic; applies to specific validation/context patterns |
| `check_endpoint_metadata` | Applies only when `azure-functions-validation` is a dependency; heuristic route detection |
| `check_openapi_version_mixing` | Heuristic signal detection across OpenAPI 3.0/3.1 usage |
| `check_scan_before_spec` | Call-order heuristic; naming-based detection may miss custom flows |
| `check_langgraph_anonymous_auth` | Applies only to LangGraph projects; heuristic auth-level detection |

---

### Tier 3 — Experimental Rules

Experimental rules are based on:

- Real-world troubleshooting experience
- Heuristic detection of common patterns
- Operational best practices not codified in Microsoft Learn

These rules **may produce false positives** and must be **opt-in only** — they must
never appear in the built-in `v2.json` with `"required": true`, and are better suited
for community-contributed custom rule files.

Experimental rules must not be promoted to Extended or Core without:

1. A documented Microsoft Learn or Azure SDK reference
2. At least one cycle of community feedback confirming low false-positive rate
3. A test covering both pass and non-pass outcomes

#### Examples (not yet built-in)

| Rule | Reason |
|---|---|
| `blueprint_registration_missing` | Project structure heuristic; high false-positive risk |
| `deployment_layout_warning` | Packaging layout suggestion; project-specific |
| `logging_configuration_missing` | Operational recommendation; not in official required config |

---

## Deterministic Rule Requirement

Core rules must rely on **deterministic, static checks**.

**Allowed check types for Core rules:**

| Type | Description |
|---|---|
| `file_exists` | File present at project root |
| `host_json_version` | JSON property equality |
| `package_declared` | Package name appears in requirements.txt (falls back to pyproject.toml) |
| `dependency_manifest` | Dependency file (requirements.txt or pyproject.toml) exists |
| `compare_version` | Version comparison against a fixed minimum |

**Not allowed in Core rules:**

- `source_code_contains` — source pattern matching can match unrelated code
- `callable_detection` — heuristic; non-standard callables may not be detected
- `file_glob_check` — glob patterns can match intentionally kept files
- `conditional_exists` — result depends on heuristic detection of features in source
- `any_of_exists` with environment variables — environment-dependent; not static

Rules using these check types belong in Extended or Experimental tiers.

---

## CI Safety Principle

Core rules must be **safe to enforce as CI hard blockers**.

A rule should produce a `fail` result (and non-zero exit code) only when:

1. The configuration is clearly invalid per official documentation
2. The fix is unambiguous (no judgment required)
3. The rule is grounded in a specific Microsoft Learn page

If any of those conditions is not met, the rule must be `"required": false`
so it produces a `warn` result that does not fail CI by default.

---

## Microsoft Learn Anchoring

Every built-in rule should reference its documentation basis via `hint_url`.
Rules without a documentation anchor belong in the Experimental tier until a reference is found.

### Relevant Reference Pages

| Topic | URL |
|---|---|
| host.json reference | https://learn.microsoft.com/azure/azure-functions/functions-host-json |
| Python developer reference | https://learn.microsoft.com/azure/azure-functions/functions-reference-python |
| Supported Python versions | https://learn.microsoft.com/azure/azure-functions/functions-reference-python#supported-python-versions |
| Managing dependencies | https://learn.microsoft.com/azure/azure-functions/functions-reference-python#managing-dependencies |
| Programming model v2 (decorators) | https://learn.microsoft.com/azure/azure-functions/functions-reference-python?pivots=python-mode-decorators |
| Extension bundles | https://learn.microsoft.com/azure/azure-functions/extension-bundles |
| local.settings.json | https://learn.microsoft.com/azure/azure-functions/functions-develop-local#local-settings-file |
| Application Insights | https://learn.microsoft.com/azure/azure-monitor/app/azure-functions |
| Core Tools v4 | https://learn.microsoft.com/azure/azure-functions/functions-run-local#v4 |
| Durable Functions | https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview |
| .funcignore | https://learn.microsoft.com/azure/azure-functions/functions-run-local#funcignore |

---

## Rule Identity, Severity, and Tier Metadata

As of the rule-model refactor, the schema and runtime model rule **identity**,
**severity**, **gate**, and **tier** explicitly instead of overloading `required`.
Each emitted check result carries a stable `rule_id` (used directly by the SARIF
reporter — no fragile reverse-mapping from the human-readable label).

```json
{
  "id": "check_host_json",
  "severity": "error",
  "gate": true,
  "tier": "core"
}
```

| Field | Values | Purpose |
|---|---|---|
| `severity` | `error`, `warning`, `info` | Runtime severity of a failing rule. A failing `error` rule maps to `fail`; otherwise it maps to `warn`. |
| `gate` | `true`, `false` | Whether a failing rule fails its section (gates the run), independent of severity. |
| `tier` | `core`, `extended`, `experimental` | Explicit maturity/tier classification. |

All three are **optional** and backward compatible: when omitted they are derived
from `required` (`severity` → `error`/`warning`, `gate` → the `required` value,
`tier` → `core`/`extended`). This keeps existing `v2.json` entries valid while
allowing rules to specify the three concerns independently.

### Proposed Future Metadata

The following optional fields remain reserved for future schema extensions.
They are **not currently enforced** by the schema or handler runtime.

```json
{
  "id": "check_host_json",
  "source_type": "ms_learn",
  "source_title": "Azure Functions host.json reference",
  "source_url": "https://learn.microsoft.com/azure/azure-functions/functions-host-json"
}
```

| Field | Values | Purpose |
|---|---|---|
| `source_type` | `ms_learn`, `derived`, `heuristic` | Classification of rule's documentation basis |
| `source_title` | String | Human-readable title of the source document |
| `source_url` | URI | Direct link to the authoritative reference |

To adopt these fields, update `rules.schema.json`, the `Rule` TypedDict in `handlers/_helpers.py`,
and all entries in `v2.json`.

---

## Rule Lifecycle

### Promoting a rule from Extended → Core

A rule may be promoted to Core (i.e., `"required": true`) only when:

- [ ] It passes all Tier 1 requirements above (deterministic, MS Learn anchor, near-zero FP)
- [ ] A test covers the pass, fail, and edge-case outcomes
- [ ] The change is documented in `CHANGELOG.md` as a **breaking change** (semver major)
- [ ] `minimal_profile.md` is updated to reflect the new minimal rule set

### Demoting a rule from Core → Extended

A rule must be demoted to Extended (i.e., `"required": false`) when:

- Evidence of false positives in real projects emerges
- The underlying check becomes environment-dependent (not project-static)
- The Microsoft Learn reference changes or is removed

Demotions are also **breaking changes** because they change the `--profile minimal` set
and affect the exit code behavior of CI pipelines that relied on the rule to fail.

---

## Summary

The guiding principle for rule design is:

> **Prefer fewer rules with high confidence over many rules with uncertainty.**

`azure-functions-doctor` should remain:

- **Predictable** — the same project produces the same result on any machine
- **Low-noise** — warnings should be meaningful, not routine
- **Grounded in official documentation** — every rule should have a citable source

[py-versions]: https://learn.microsoft.com/azure/azure-functions/functions-reference-python#supported-python-versions
[req-txt]: https://learn.microsoft.com/azure/azure-functions/functions-reference-python#managing-dependencies
[az-func-lib]: https://learn.microsoft.com/azure/azure-functions/functions-reference-python
[host-json]: https://learn.microsoft.com/azure/azure-functions/functions-host-json
[durable-determinism]: https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-code-constraints
