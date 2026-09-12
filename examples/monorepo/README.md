# Monorepo example

A project nested under `services/api`. Anchors the SARIF repo-root rebasing
contract: scanning `--path services/api` must prefix every artifactLocation
URI with `services/api/` (issue #392). `host.json` is intentionally missing
so both SARIF branches (located file + scan-root fallback) are exercised.
