# Catalog Operations

How the version-controlled compatibility catalog is maintained, verified, and
consumed. The catalog is the **single source of truth** for Azure version
knowledge: handlers never hardcode dates or support matrices.

## Where the catalog lives

- Facts: `src/azure_functions_doctor/assets/compatibility/catalog.json`
- Loader/model: `azure_functions_doctor.compatibility` (`load_catalog()`)
- Each fact carries `fact_id`, `applies_to`, `status`, `support_end`
  (value + precision), `source_url`, `last_verified`, and
  `verification_notes`.

## Update procedure

1. **Identify the drift.** The weekly maintenance workflow
   (`.github/workflows/maintenance.yml`) fails when
   `catalog.last_verified` is older than 30 days, or when a fact's upstream
   source changes (found manually or via the freshness sweep).
2. **Re-verify against the source.** Open every fact's `source_url` and
   confirm the dates/statuses. `support_end.precision` records what the
   source actually publishes — `day`, `month`, or `year` — and comparisons
   always widen to the last calendar day of that precision (never narrower).
3. **Edit `catalog.json`.** Update `status`/`support_end` per the source; set
   the fact's `last_verified` to the re-verification date; extend
   `verification_notes` with a one-line quote of the source sentence that
   justifies the change.
4. **Bump `catalog_version`** (semantic: new/changed facts = minor, removed
   facts = major) and the top-level `last_verified`.
5. **Run the gates**: `hatch run pytest` (the verdict matrix in
   `tests/test_catalog_verdict_matrix.py` is *derived from the catalog*, so
   it stays green automatically), plus the standard style/typecheck.

The runtime never fetches the network — catalog updates are a
commit-time operation, keeping every verdict offline and reproducible.

## Freshness policy

- The shipped runtime is **100% offline**; freshness is a *governance*
  concern, not a runtime one.
- The weekly maintenance job fails when `last_verified` is >30 days old.
  30 days matches the cadence at which Microsoft publishes lifecycle
  changes; a failing weekly job is the alert, and the fix is the update
  procedure above (never silencing the gate).
- Findings expose provenance so consumers can audit staleness themselves:
  `last_verified`, `source_url`, and `catalog_version` ride along in the
  JSON output and SARIF properties.

## Incomplete target configuration

The doctor resolves the deployment target from infra config (bicep/ARM)
and `local.settings.json`. When information is missing, rules **skip
explicitly rather than guess**:

| Missing input | Behavior | What to supply |
| --- | --- | --- |
| Any deploy config (no bicep/ARM) | Flex family + `linuxFxVersion` + dev-storage skip | Infra templates in the project (or run with `--profile development`) |
| `hosting_plan` undeterminable | Hosting-plan lifecycle + Functions runtime lifecycle skip | `hostingPlan`/plan-bearing infra (`--hosting-plan` where supported) |
| Not a Flex Consumption app | The three Flex rules skip | Nothing — out of scope by design |
| `local.settings.json` absent | `FUNCTIONS_EXTENSION_VERSION` check skips | A `local.settings.json` with `Values` |
| Target Python unknown | Python lifecycle uses the running interpreter | `--target-python` |
| `git` unavailable | local.settings git-tracking skips | Run inside a git checkout |
| `azure-functions-validation` not declared | Endpoint-metadata rule skips | Declare it or ignore the skip |

Skips are first-class statuses (`"skip"` in the JSON contract) — they never
gate and never count as findings in SARIF.
