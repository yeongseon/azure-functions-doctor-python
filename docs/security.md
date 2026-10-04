# Security

The azure-functions-doctor project maintains a commitment to providing a secure tool for diagnosing Azure Functions local development environments. This document outlines the security policies, reporting processes, and the trust model for using and extending the tool.

## Reporting Vulnerabilities

We take security issues seriously. If you discover a vulnerability, please report it through the following channels:

### Preferred: GitHub Security Advisory
The most secure and efficient way to report a vulnerability is through the GitHub Security Advisory system at:
https://github.com/yeongseon/azure-functions-doctor/security/advisories/new

### Alternative: Email
You can also report security concerns via email to:
yeongseon.choe@gmail.com

### What to Include
When reporting a vulnerability, please include:
- A clear description of the vulnerability and its potential impact.
- Detailed reproduction steps, including any sample code or configuration files.
- An assessment of the impact on users or environments.
- A suggested fix or mitigation, if you have one.

### Response Timeline
- Initial acknowledgment: Within 48 hours.
- Status updates and triage: Within 7 days.
- Full resolution: We aim to provide a fix or public disclosure within a reasonable timeframe, depending on the severity and complexity of the issue.

### Responsible Disclosure
We ask that you follow responsible disclosure practices. Please do not share information about the vulnerability publicly until we have had a chance to address it and notify affected users.

## Supported Versions

| Version | Supported |
| :--- | :--- |
| Latest release | Yes |
| Older releases | No |

Security fixes are only applied to the most recent stable release. Users are encouraged to stay updated with the latest version.

## Security Scanning

To ensure the integrity of our codebase, we employ several automated security scanning tools:

- **Bandit (1.9.4)**: A static analysis security scanner that identifies common security issues in Python code.
- **Scope**: Scans all files in the `src/` directory while excluding the `tests/` directory to focus on production code.
- **Local Execution**: You can run the security scan locally using `make security` or `hatch run security`.
- **CI Integration**: The `security.yml` workflow runs Bandit on every push and pull request to the main repository.
- **Pre-commit**: Bandit is integrated as a pre-commit hook, ensuring that potential issues are caught before code is committed.

## Security Scope

### Within Scope
- **Diagnostic Rule Integrity**: Rules do not import or execute scanned Python modules. The core logic evaluates project files and may invoke documented local tools such as Git and Azure Functions Core Tools.
- **Git Isolation**: The local-settings tracking check runs `git ls-files` with repository-configured filesystem monitors disabled and hooks redirected to the operating system null device. This prevents repository Git configuration from executing hook or fsmonitor programs during the scan.
- **Custom Rules Trust Boundary**: When a user specifies a custom `rules.json` path, that file is treated as a trusted input.
- **Network Behavior**: The documented diagnostics and version checks do not make outbound network requests. The Azure Functions Core Tools version check invokes the locally installed `func` CLI via a subprocess rather than contacting a remote registry.
- **Input Validation**: Path arguments and user-provided inputs are validated to prevent common vulnerabilities like path traversal.
- **Dependency Security**: We monitor our runtime dependencies (jsonschema, packaging, rich, typer, and `tomli` on Python < 3.11) for known vulnerabilities.

### Out of Scope
- **Diagnosed Project Security**: The security posture of the Azure Functions projects being analyzed is the responsibility of the project owner.
- **Azure Functions Runtime Security**: Issues related to the Azure Functions runtime or platform are managed by Microsoft.
- **Build-time Security**: Security during the build or deployment phase of the projects being checked is outside the scope of this tool.

## Network Behavior

- **No Outbound Requests**: The documented diagnostics and version checks do not contact remote servers. The Azure Functions Core Tools version check runs the locally installed `func` CLI as a subprocess and compares the reported version locally.
- **Privacy**: No telemetry, analytics, or user data is collected or sent to any remote servers.
- **Resilience**: Checks that depend on external tooling (such as the `func` CLI) are designed to fail gracefully. If the tool is unavailable, the handler returns a `fail` result which is then surfaced as a `warn` because the rule is optional — the process does not crash.

> Note: some diagnostic rules scan user project code for risky patterns such as `requests.get(...)` calls. These are string patterns detected in the analyzed project — they are not runtime dependencies or network calls made by `azure-functions-doctor` itself.

## Custom Rules Trust Model

- **Assumption of Trust**: Custom `rules.json` files provided via the `--rules` flag are assumed to be from a trusted source.
- **User Responsibility**: Users should only load custom rules from sources they trust.
- **Execution Limits**: Custom rules define metadata for checks and cannot execute arbitrary scripts or binary code.
- **Handler Types**: Rule execution is limited to a pre-defined set of built-in handlers (such as `file_exists`, `path_exists`, etc.), which provides a controlled environment for diagnostic logic.

## Security Best Practices for Users

- **Update Frequently**: Keep your installation of `azure-functions-doctor` updated to benefit from the latest security patches and rule improvements.
- **Review Custom Rules**: Always review the contents of a custom rules file before using it with the doctor.
- **Automation**: Use the `--format json` output for integration into automated CI/CD pipelines for consistent security and environment checks.
- **GitHub Integration**: Use the SARIF output format to integrate results directly with GitHub Code Scanning.

## Dependency Security

The project relies on a minimal set of runtime dependencies:
- **jsonschema**: For validating rule files and configurations.
- **packaging**: For handling version comparisons.
- **rich**: For formatted terminal output.
- **typer**: For building the command-line interface.
- **tomli**: For parsing `pyproject.toml` on Python < 3.11 (the standard-library `tomllib` is used on 3.11+).

We use Dependabot to monitor these dependencies and provide automated updates for security vulnerabilities and version upgrades. All chosen dependencies are widely-used and actively maintained packages.
