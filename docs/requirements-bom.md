# UTF-8 BOM requirements includes

Requirements include discovery accepts a leading UTF-8 byte order mark before
`-r` / `--requirement` directives, including in nested files and CRLF files.
The shared directive parser removes that leading marker before recognizing pip
include syntax; containment, cycle/depth and inspection budgets are unchanged.

## Behavior change for the next release

Previously, a BOM before the first include in `requirements.txt` could hide
`azure-functions` declared in the included file. Doctor then reported the
required package missing and exited 1. The same valid project now passes that
check and can exit 0 when its other required checks pass. Table, JSON and SARIF
use the same corrected result. This note documents the release-facing behavior
without editing the Release Please-owned changelog or version.
