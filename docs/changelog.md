# Changelog

All notable changes to this project will be documented in this file.

**Versioning Scheme**:
- Follows Semantic Versioning (semver.org)
- Version numbers: MAJOR.MINOR.PATCH
- Breaking changes listed explicitly

## Full Version History

### v0.20.0 (2026-09-06)

**Migration notes** (read before upgrading pinned `@v1` Action usage):

1. **GitHub Action default profile is now `deploy`** (was `minimal`). Pinned
   `yeongseon/azure-functions-doctor@v1` users receive this automatically on
   release: the run grows from 6 required rules to 19 (6 required + 13
   optional deploy-correctness rules). The exit-code contract is unchanged —
   the added rules only warn and `fail-on-warn` defaults to `false` — but
   expect more Code Scanning alerts. Pin `profile: minimal` explicitly to
   keep the previous behavior.
2. **SARIF now emits one result per finding** (was one per rule). Rules that
   report multiple findings (e.g. uncovered routes, unpinned requirements)
   produce one located result each, compounding the alert-count increase
   above with more precise locations.
3. **`check_unsupported_metadata_version` was removed.** `[tool.azure-functions-doctor].ignore`
   entries naming this rule ID are now dangling; remove them.

Other highlights: SARIF artifactLocation URIs are repo-root-relative with
`partialFingerprints` (was: absolute paths in some branches); all file
traversal honors the shared exclusion helper and the user's `exclude` globs
(no more venv/node_modules false positives); `--version` flag; the `doctor`
subcommand is optional; reference examples pass their own pinning rule.


### v0.16.2 (2026-03-29)
- Fix 6 confirmed bugs: #95, #96, #97, #98, #99, #100 (#101)
- Update README with Azure Functions Python DX Toolkit branding
- Rename publish environment from production to release
- Unify CI/CD workflow configurations

### v0.15.1 (2026-03-14)
- Unified tooling: Ruff (lint + format), pre-commit hooks, standardized Makefile
- Comprehensive documentation overhaul (MkDocs site with standardized nav)
- Translated README files (Korean, Japanese, Chinese)
- Standardized documentation quality across ecosystem

### v0.15.0
- Fixed doctor workflow and docs build
- Standardized repository planning documents
- Added demo (VHS-based terminal demo with pass/fail contrast)
- Documented example coverage policy
- Raised test coverage for utility paths
- Pinned docs dependencies

### v0.14.0
- Translated remaining Korean to English
- Added forbid-korean pre-commit hook enforcement
- Added SARIF and JUnit output formats
- Added minimal rule profile (--profile minimal)
- Included metadata in JSON output
- Added custom rules.json option (--rules flag)
- Added error context logging for handlers
- Normalized Makefile targets
- Upgraded dev tool versions
- Excluded common directories from source scan
- Aligned docs with current implementation
- Added rules and schema consistency tests

### v0.13.0
- Required 'azure-functions' instead of deprecated 'azure-functions-python-library'
- Corrected indentation and typing for package_declared handler
- Simplified CI configuration (skip pre-commit in CI, pin hatch)
- Bypassed hatch for direct mkdocs build in CI

### v0.12.0
- BREAKING: Removed severity field and simplified status model
- Updated usage examples for concise messages
- Shortened handler detail strings
- Unified status icons (pass/warn/fail)
- Added icons and status legend
- Renamed examples (v2/basic-hello to http-trigger, v1/HttpExample to http-trigger)
- Added v1 multi-trigger sample
- Added installation steps and CLI usage docs
- Split examples into v2/multi-trigger and v1/HttpExample

### v0.11.0
- Merged handler tests into single file
- Added type hints to tests

### v0.10.0
- Renamed command to 'azure-functions doctor' and updated UI
- Included severity metadata and normalized statuses
- Updated CLI name references

### v0.9.0
- Renamed subcommand to 'doctor'
- Added 'azure-functions' console script entrypoints
- Replaced 'func-doctor' with 'azure-functions' in docs

### v0.8.0
- Formatter adjustments (black/ruff)

### v0.7.0
- Added conditional_exists and callable_detection handlers
- Added v1/v2 rule stubs and severities
- Simplified rule loader, added allow_v1 flag for CLI

### v0.6.0
- Improved rich console output formatting
- Enhanced JSON output structure for better machine readability
- Updated core diagnostic engine for faster processing

### v0.5.0
- Added package_declared handler for dependency validation
- Added source_code_contains handler for code-level checks
- Expanded v1.json and v2.json rule sets
- Integrated initial GitHub Actions for CI

### v0.4.0
- Added file_exists and path_exists handlers
- Introduced executable_exists and compare_version handlers
- Established base rule schema for Azure Functions validation

### v0.3.0
- Implemented core rule-based check system
- Added support for v1 and v2 Azure Functions models
- Developed Typer-based CLI interface
- Integrated Rich for terminal UI components

### v0.2.0
- Refined diagnostic engine architecture
- Setup pytest test suite with initial handler tests
- Defined project structure for modular handlers and rules

### v0.1.0
- Initial release with core diagnostic engine
- Basic CLI structure and terminal output
- Fundamental file and path validation handlers
- Support for basic rule loading from JSON
