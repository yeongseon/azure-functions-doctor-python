# Python scan parse reuse

Doctor reuses successful Python ASTs during model detection and, separately,
during rule execution. Each phase owns a context-local cache of at most 128
source strings. Leaving the phase discards it, including on exceptions;
separate scans cannot reuse stale trees. Cache overflow simply parses normally.
Failures are not cached, so each detector retains its existing exception policy.
Detectors treat the shared ASTs as read-only.

File reads, exclusions and bounded inspection are deliberately unchanged:
inspection gaps still belong to the rule that observes them. This is not a
persistent file cache, plugin framework or new public command.

## Measurement

Python 3.11.15, repository `examples/v2/multi-trigger`, measured before runtime
changes: minimal 8 reads / 5 parses / 0.01324s; full 34 reads / 20 parses /
0.12604s. After the change: minimal 8 / 2 / 0.01331s; full 34 / 2 / 0.11405s.
These are individual instrumented runs, not a statistically significant speed
claim. Filesystem traversal and external tool probing can dominate small apps.

The repository instrumentation can also compare the same checkout with caching
disabled using `DOCTOR_UNCACHED=1`. It reports a SHA-256 digest of the complete,
ordered per-rule results (including locations, severities and details). A paired
run produced:

| Profile | Uncached reads/parses/time | Cached reads/parses/time | Equal result digest |
| --- | --- | --- | --- |
| minimal | 8 / 5 / 0.01398s | 8 / 2 / 0.01309s | `d1bdad64752147dc13c97bfa72fd8347c4e8fc22b5a8cf1190f32949b1bbbddd` |
| full | 34 / 20 / 0.11880s | 34 / 2 / 0.12250s | `231b601966950c60ba8238dd935ad33ff6dd6006c0069a9ae7c705206333aff3` |

The stable benefit is eliminating repeated parses (60% minimal, 90% full), not
an asserted end-to-end speedup. Existing table/JSON/SARIF byte baselines remain
unchanged. Characterization tests cover malformed/undecodable sources, repeated
scans and changed files; cache tests cover nested phases, overflow and failures.
