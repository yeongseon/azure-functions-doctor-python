# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please report it
responsibly and avoid public disclosure until a fix is available.

### Preferred: GitHub Security Advisory

1. Go to the [Security Advisories page](https://github.com/yeongseon/azure-functions-doctor-python/security/advisories/new)
2. Click "Report a vulnerability"
3. Submit the details in the private advisory

### Alternative: Email

If you prefer email, contact: yeongseon.choe@gmail.com

### What to Include

* A clear description of the issue
* Steps to reproduce
* Impact assessment
* Suggested mitigation or fix, if available

### Response Timeline

* Initial response: within 48 hours
* Status update: within 7 days

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Latest release | :white_check_mark: |
| Older releases | :x: |

## Security verification and evidence

Security scan results are a **code/config review finding until runtime impact is
independently demonstrated**. A clean static scan is not Azure certification.

| Where | Control | Blocking behavior |
| --- | --- | --- |
| Pull requests, main, weekly, manual | Existing Bandit plus exact-inventory evidence and pinned Semgrep action | Failures block their jobs; repository branch protection determines required checks |
| Existing workflows | CodeQL and SBOM | Preserved independently; not replaced by Bandit |
| Release tag | `runtime-dependency-audit`, Python 3.11–3.14 | Required by `publish`, alongside library, doctor-runtime and Azure certification gates |
| Scheduled dependency audit | Runtime wheel closure | Blocking job status |
| Scheduled dependency audit | Development environment | Reporting-only, visibly nonblocking |

The runtime gate installs the **single exact candidate wheel** from the build
artifact into an isolated `venv --without-pip`. The audit tool
(`pip-audit==2.10.1`) runs outside that installation and audits only its
site-packages. Candidate name/version from the wheel METADATA must match the installed
distribution before excluding only that first-party candidate. The exact installed
third-party inventory is audited as pinned requirements with `--no-deps --disable-pip`,
so unpublished candidate versions do not require a PyPI entry. Missing/mismatched
identity, empty inventory and third-party skips still block. No production runtime extras are currently declared; `dev` and
`docs` are not production closures. Adding a production extra requires updating
the audited matrix. All known runtime advisories block, including UNKNOWN
severity because the upstream feed need not provide consistent severity data.

`PASS` exits 0; findings (`FAIL`) exit 1; scanner/policy failure (`TOOL_ERROR`)
exits 2; empty, skipped or mismatched scope (`INCOMPLETE`) exits 3. Every nonzero
status blocks publishing. Tool failure is never described as “no vulnerabilities.”
Evidence upload uses `if: always()` and fails on missing files. If tool setup
itself fails before evidence can be generated, the failed job and missing
artifact remain visible; that is not a clean scan.

Bandit scans every Python file on disk in `src/`, `examples/`, `demo/`,
`scripts/`, and `tools/`, with exact inventory matching and a nonempty LOC/file
floor. Tests, virtual environments, and generated docs are not product scan
surfaces. The Action entrypoint is Bash, not Python; it is reviewed separately.
Existing inline `# nosec` annotations are retained and audited using
`--ignore-nosec` against exact rule/file/line allow-lists. A changed annotation
inventory fails completeness. Semgrep evidence records the pinned action's
outcome only: its finding count is unknown, not zero. A successful action without
structured scan evidence is `INCOMPLETE` ("action outcome only"); the evidence target
tolerates only exit 3 while the pinned action remains the blocking gate.

Local entry points are `make security` (including the expanded Bandit inventory),
`make security-bandit`, `make security-semgrep`, `make security-types`,
`make security-audit` (blocking), and `make security-audit-report` (reporting workflow).
For audits supply `AUDIT_SITE_PACKAGES` plus `CANDIDATE_WHEEL`, or the independently
expected `CANDIDATE_NAME` and `CANDIDATE_VERSION`. `SECURITY_PYTHON` selects the tooling
interpreter and `SECURITY_OUTPUT` selects the evidence directory.

The JSON evidence and GitHub summary retain IDs, relative paths, lines,
severities/confidences, counts, tool versions and applied exception identifiers.
They discard raw scanner messages, code excerpts, stderr, advisory descriptions,
exception payloads, connection strings and authorization headers. This guarantee
applies to helper-generated evidence, not arbitrary third-party action logs or
operator-provided filenames. Treat paths and setting names as potentially
sensitive metadata; do not put credentials in them.

### Exceptions and recovery

Policies are in `security/bandit-policy.json` and
`security/dependency-audit-policy.json`. Each exception needs an exact rule or
advisory ID, exact file/line or normalized package, reason, owner, added date and
expiry **at most 90 days after addition**. Duplicate, malformed, future-dated or
expired exceptions fail closed. Dependency exceptions are `not-affected` or
`fix-not-available`; a no-fix exception stops applying when a fixed version
exists. Static `reviewed-static` entries document reviewed scanner observations,
not a demonstrated runtime exploit. Review stale entries rather than widening
them. There are no runtime advisory exceptions initially.

Keep least-privilege permissions, SHA-pinned actions, PyPI OIDC, exact-artifact
reuse, and the existing Azure certification chain. Recover a transient failure
with `gh workflow run publish-pypi.yml --ref vX.Y.Z` against the unchanged existing
tag. A code correction requires fixing forward and a new release; never move a
tag or bypass a failed/incomplete audit.

## Inspection trust assumptions and current limits

Doctor statically parses project source; it does not import `function_app.py`,
execute `setup.py`, evaluate IaC, or install project dependencies during ordinary
inspection. Custom `--rules`, CLI arguments, output destinations, the installed
tool, Python environment and executables on PATH are **operator-trusted**.
The Action's `install-project-deps` is false by default: enabling it executes
package installation/build hooks and is unsafe for untrusted pull requests.

Regression tests cover synthetic secrets in settings/source, table/JSON/SARIF/
JUnit artifacts and summary sidecars, the public API and generated-report agent
adapter; invalid runtime/host values are masked or omitted without changing
finding status, rule IDs, remediation or Finding Contract v2. Unknown application
settings are not dumped. Nested handled exceptions retain category/operation,
not payloads or chained tracebacks. Recognized runtime pins remain visible.
The agent adapter consumes existing reports; it is not a sanitizer for
arbitrary externally supplied reports.

Project discovery rejects resolved out-of-root symlink files and does not follow
symlink directory loops. Requirements includes cannot leave the top-level
manifest directory in both flattened and location-preserving rule walkers. Shared source and local/deployment-setting reads reject
symlinks, FIFOs/devices, binary NUL content and files over 4 MiB. These protections
are **not yet universal**: several legacy host/requirements/TOML readers still
read directly, JSON depth/duplicate-key behavior is parser-defined, and concurrent
filesystem replacement is not a hardened sandbox. Pre-open regular-file checks
avoid opening known nonregular paths when platform nonblocking flags are unavailable;
they do not prevent concurrent replacement. Nested IaC remains part of the
selected tree and can contribute deployment signals. Do not scan actively hostile
trees in a privileged environment; use a disposable credential-free container,
read-only mount, resource limits and trusted PATH.

The two runtime subprocess sites use argument arrays and 10-second timeouts.
Git metadata queries disable fsmonitor/hooks; injected shell syntax remains one
path argument. Captured output is not yet size-bounded, and the trusted Core
Tools executable can emit arbitrary output. Further hardening is required before
claiming hostile executable or unlimited-output resistance.

## Infrastructure and examples

`infra/main.bicep` is real-Azure e2e infrastructure, not a production security
template. Review confirms HTTPS-only Functions, storage TLS 1.2 and disabled
public blob access; it still uses storage account keys, public networking and an
Application Insights connection-string output. Validate managed-identity storage,
private networking, identity/RBAC and removal of the telemetry output on Azure
before changing that certification fixture. No Azure resources were provisioned
for this review.

Examples and demo fixtures include intentionally broken configuration, emulator
storage and anonymous HTTP routes for diagnostics. They are local/test-only,
not secure production defaults. Production deployments require explicit
authentication/authorization, TLS, scoped identities and secret-free CI logs.
The composite Action passes inputs through quoted environment variables rather
than interpolating them into shell script text. A real Bash regression probe
proved and now prevents command-substitution execution through the project path.
Input destinations and dependency installation remain operator-controlled; the
Action is not a sandbox for hostile workflows.
