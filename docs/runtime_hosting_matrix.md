# Python Runtime Diagnostics Across Hosting Plans

The same Python version can be treated differently depending on the hosting plan you
select with `--hosting-plan`. This page runs one checked-in synthetic project,
`examples/v2/http-trigger`, through a small matrix of two plans and two Python
targets. Everything is offline and read-only: no Azure subscription, credentials, or
Core Tools are needed, and the plan and Python version come only from CLI flags.

## Run the matrix

```bash
azure-functions-doctor doctor --path examples/v2/http-trigger --profile deploy --hosting-plan linux-consumption --target-python 3.12
azure-functions-doctor doctor --path examples/v2/http-trigger --profile deploy --hosting-plan linux-consumption --target-python 3.13
azure-functions-doctor doctor --path examples/v2/http-trigger --profile deploy --hosting-plan flex-consumption --target-python 3.12
azure-functions-doctor doctor --path examples/v2/http-trigger --profile deploy --hosting-plan flex-consumption --target-python 3.13
```

## What you should see

| Hosting plan | Python | Result |
| --- | --- | --- |
| `linux-consumption` | `3.12` | Runs, exit `0`. `check_python_runtime_lifecycle` passes; `check_hosting_plan_lifecycle` passes and reports the plan's catalog retirement date. |
| `linux-consumption` | `3.13` | Rejected before any rule runs: usage error, exit `2` (`Python 3.13 is not supported on the 'linux-consumption' hosting plan`). |
| `flex-consumption` | `3.12` | Runs, exit `0`. `check_hosting_plan_lifecycle` passes with "no published retirement date". |
| `flex-consumption` | `3.13` | Runs, exit `0`. Same plan verdict; `check_python_runtime_lifecycle` reports the Python 3.13 support end from the catalog. |

Two different mechanisms are involved:

- **Plan/version support** (exit `2`): the Python x plan combination is checked against the
  catalog's hosting-plan matrix before diagnostics start. A rejected combination is an input
  error, not a diagnostic finding.
- **Lifecycle findings** (rule results): `check_python_runtime_lifecycle` depends only on the
  Python version's support-end date; `check_hosting_plan_lifecycle` depends only on the
  plan's retirement date.

These verdicts are version- and date-bound policies from the compatibility catalog, not
a guarantee about what Azure accepts today. The tests do not hardcode Azure claims: they
derive expectations from the catalog and pin "today" so results do not change as calendar
dates pass. A clean run is not certification of any deployed resource.

## Updating when the support catalog changes

When the compatibility catalog changes (a plan gains or loses a Python version, or a
runtime or plan retirement date moves), update this example in the same change:

1. Edit the catalog and run `pytest tests/test_compatibility.py tests/test_catalog_verdict_matrix.py --no-cov`.
2. Run `pytest tests/test_runtime_hosting_matrix.py --no-cov`. Because expectations come from
   the catalog, most changes need no edit. If a pair stops being supported, the test already
   expects the exit-`2` rejection.
3. If a pair you document here changes behavior, edit the `MATRIX` list in
   `tests/test_runtime_hosting_matrix.py` and the table above together.
4. Keep the `TODAY` constant in the test before every catalog retirement date, or choose a
   new pinned date deliberately.
