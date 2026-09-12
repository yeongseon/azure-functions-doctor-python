# JSON Output Contract

`--format json` produces the primary machine-readable output contract for automation.

This page defines field meanings, stability guarantees, and parser examples.

## Emit JSON

```bash
azure-functions-doctor doctor --format json --output doctor.json
```

If `--output` is omitted, JSON is printed to stdout.

## Top-level shape

```json
{
  "schema_version": "2.0",
  "metadata": {
    "tool_version": "0.19.2",
    "generated_at": "2026-09-06T10:40:20.731Z",
    "target_path": "/absolute/path/to/project",
    "programming_model": "v2",
    "target_python": null,
    "deployment_mode": "remote-build",
    "hosting_plan": null
  },
  "results": [
    {
      "title": "Python Env",
      "category": "python_env",
      "status": "fail",
      "items": [
        {
          "rule_id": "check_python_runtime_lifecycle",
          "label": "Python runtime lifecycle",
          "value": "Python 3.10.12 support is expected to end in October 2026; plan an upgrade to a newer supported Python (e.g. 3.14) before then.",
          "status": "warn",
          "severity": "warning",
          "tier": "core",
          "evidence": "Python 3.10.12 support is expected to end in October 2026; plan an upgrade to a newer supported Python (e.g. 3.14) before then.",
          "expected": "A supported Azure Functions Python runtime",
          "actual": "Python 3.10.12 (support ends October 2026)",
          "source_url": "https://learn.microsoft.com/azure/azure-functions/supported-languages",
          "last_verified": "2026-09-06",
          "catalog_version": "1.0.0",
          "analysis": { "type": "deterministic" },
          "hint": "Target a Python version with a long support runway. Upgrade a retiring runtime before its Azure Functions end-of-support date.",
          "hint_url": "https://learn.microsoft.com/azure/azure-functions/supported-languages"
        }
      ]
    }
  ]
}
```

## Field reference

### Location semantics

Findings carry `file`/`line` (single-location form) or `locations` (per-finding
form) whenever the rule can attribute a project artifact. Environment-level
checks (virtual environment, Python executable, Core Tools, interpreter
lifecycle) intentionally have **no file location** and fall back to the
scan-root URI — that is the correct semantic, not a gap.

### Machine-readable schema

The contract ships as a JSON Schema in the wheel: [`schemas/output-contract-2.0.schema.json`](https://github.com/yeongseon/azure-functions-doctor-python/blob/main/src/azure_functions_doctor/schemas/output-contract-2.0.schema.json) (draft-07). Consumers validate with `jsonschema`:

```python
import json, jsonschema
schema = json.load(open("output-contract-2.0.schema.json"))
jsonschema.validate(json.load(open("doctor-report.json")), schema)
```

Strict on identity and semantics (rule_id shape, status/severity/tier enums); permissive on additive fields for 0.x evolution. Field *meaning* changes require a migration note per the [semver policy](semver_policy.md).

### Top level

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Machine-output schema version (Finding Contract). Current: `"2.0"`. Independent of the SARIF schema version (`"2.1.0"`). |

### `metadata`

| Field | Type | Description |
| --- | --- | --- |
| `tool_version` | string | Installed `azure-functions-doctor` version. |
| `generated_at` | string | UTC timestamp in ISO 8601 format. |
| `target_path` | string | Resolved absolute project path used for checks. |
| `programming_model` | string | Detected Azure Functions programming model (`v2`, `mixed`, `unsupported_v1`, or `unknown`). |
| `target_python` | string \| null | Target Python version requested via `--target-python`, or `null` when not set. |
| `deployment_mode` | string | Deployment mode used for dependency checks: `remote-build` (default) or `local`. |
| `hosting_plan` | string \| null | Resolved hosting plan (e.g. `flex-consumption`) when determinable from deploy config, else `null`. |

### `results[]`

| Field | Type | Description |
| --- | --- | --- |
| `title` | string | Human-readable section label (display-oriented). |
| `category` | string | Stable machine-oriented section key. |
| `status` | `pass` \| `fail` | Section-level status (required-check semantics). |
| `items` | array | List of check result objects for that section. |

### `results[].items[]`

| Field | Type | Description |
| --- | --- | --- |
| `rule_id` | string | Stable machine-oriented rule identifier (matches the rule `id` in the ruleset). Used directly as the SARIF `ruleId`. |
| `label` | string | Check display label. |
| `value` | string | Diagnostic detail text from handler execution. |
| `status` | `pass` \| `warn` \| `fail` \| `skip` | Canonical item-level status. `skip` means the rule legitimately did not apply (e.g. not a Flex Consumption app); it is not an error. |
| `severity` | `error` \| `warning` \| `info` | Runtime severity of the rule. A failing `error` rule maps to `fail`; otherwise it maps to `warn`. |
| `tier` | `core` \| `extended` \| `experimental` | Rule maturity/tier classification. |
| `evidence` | string (optional) | Auditable human-readable statement backing the finding (Finding Contract v2). |
| `expected` | string (optional) | What the configuration should be, per the compatibility catalog or platform contract. |
| `actual` | string (optional) | What was actually observed. |
| `source_url` | string (optional) | Upstream source (e.g. Microsoft Learn) the verdict is pinned to. |
| `last_verified` | string (optional) | ISO date when the catalog fact was last verified against the source. |
| `catalog_version` | string (optional) | Version of the compatibility catalog the fact came from. |
| `analysis` | object (optional) | Analysis provenance block; `type` is `deterministic` for every built-in rule. |
| `locations` | array (optional) | Per-finding locations (`file`/`line`/`end_line`/`column`/`message`). SARIF emits one result per entry instead of collapsing onto the first location; the scalar `file`/`line` fields remain the single-location form. |
| `hint` | string (optional) | Human-readable remediation guidance. |
| `hint_url` | string (optional) | Supporting documentation link. |

## Stability levels

Use the following contract expectations when writing parsers.

| Field | Stability | Guidance |
| --- | --- | --- |
| `metadata.tool_version` | Stable | Safe for telemetry and compatibility checks. |
| `schema_version` | Stable | Machine-output schema version; bump only on contract-breaking change. |
| `results[].items[].evidence` / `expected` / `actual` | Stable | Finding Contract v2 auditable fields; absent on findings without catalog backing. |
| `results[].items[].source_url` / `last_verified` / `catalog_version` | Stable | Freshness/source pinning for catalog-backed findings. |
| `metadata.generated_at` | Stable | Safe for run timestamp tracking. |
| `metadata.target_path` | Stable | Safe for target correlation. |
| `metadata.programming_model` | Stable | Safe for detecting v1/v2/mixed project state. |
| `metadata.target_python` | Stable | Safe for correlating requested target Python version. |
| `results[].category` | Stable | Prefer for machine grouping. |
| `results[].status` | Stable | Safe for section-level logic. |
| `results[].items[].rule_id` | Stable | Prefer for machine matching of specific rules; used as SARIF `ruleId`. |
| `results[].items[].label` | Stable | Safe for human-readable matching. |
| `results[].items[].status` | Stable | Primary gate/filter field. |
| `results[].items[].value` | Stable | Safe for reporting detail text. |
| `results[].items[].severity` | Stable | Runtime severity classification. |
| `results[].items[].tier` | Stable | Rule maturity/tier classification. |
| `results[].title` | Detail | Display-oriented; do not hardcode behavior on casing/format. |
| `results[].items[].hint` | Detail | Helpful for UX, optional in parsers. |
| `results[].items[].hint_url` | Detail | Helpful for UX, optional in parsers. |

!!! note
    Breaking changes to stable fields require a major version bump under project semver policy.

## Status semantics

Item status rules:

- `pass`: check succeeded
- `fail`: required rule failed
- `warn`: optional rule failed
- `skip`: rule legitimately did not apply (e.g. not a Flex Consumption app, or a suppressed rule); not an error and never gates

Section status rules:

- `fail` if any required item in section failed
- otherwise `pass`

## Exit code contract

Process exit code aligns with required failures:

- `0` -> no required failures
- `1` -> one or more required failures

Always use exit code for gate truth; use JSON for diagnostics detail.

## Python parsing example

```python
import json
from pathlib import Path


def parse_doctor(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    summary: dict[str, int] = {}
    failures: list[dict[str, str]] = []

    for section in payload["results"]:
        for item in section["items"]:
            status = item["status"]
            summary[status] = summary.get(status, 0) + 1
            if status == "fail":
                failures.append(
                    {
                        "section": section["category"],
                        "label": item["label"],
                        "value": item["value"],
                        "hint": item.get("hint", ""),
                    }
                )

    return {
        "tool_version": payload["metadata"]["tool_version"],
        "generated_at": payload["metadata"]["generated_at"],
        "target_path": payload["metadata"]["target_path"],
        "summary": summary,
        "failures": failures,
    }
```

## Bash and `jq` parsing examples

Count required failures:

```bash
jq '[.results[].items[] | select(.status=="fail")] | length' doctor.json
```

List failure labels:

```bash
jq -r '.results[].items[] | select(.status=="fail") | .label' doctor.json
```

Group by status:

```bash
jq '[.results[].items[] | .status] | group_by(.) | map({status: .[0], count: length})' doctor.json
```

Extract concise report lines:

```bash
jq -r '.results[] as $s | $s.items[] | "[\($s.category)] \(.status) - \(.label): \(.value)"' doctor.json
```

## CI parser recommendations

- Prefer `results[].items[].status` for gates and counters
- Prefer `results[].category` for section grouping
- Treat `hint` and `hint_url` as optional display enrichments
- Avoid coupling logic to `title` formatting

## Common parser mistakes

- Assuming warnings fail builds
- Assuming `pass`/`warn`/`fail` are the only statuses — `skip` is a first-class status and must not crash counters
- Treating missing optional fields (`hint`, `hint_url`, and the evidence fields) as schema errors
- Parsing output from non-JSON format
- Ignoring process exit code and relying only on string matching

## Relationship to other formats

- `sarif` output follows SARIF 2.1.0 conventions
- `junit` output follows JUnit XML conventions
- This contract governs only the doctor JSON format

## Related docs

- [Usage](usage.md)
- [Diagnostics](diagnostics.md)
- [Examples: CI Integration](examples/ci_integration.md)
