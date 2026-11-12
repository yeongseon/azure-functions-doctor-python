# Release history audit: Git tags, GitHub Releases and PyPI

Status: **read-only audit (issue #671)**. No tag, GitHub Release or PyPI artifact was created, moved,
edited or deleted. Data collected on 2026-11-13 from `git ls-remote --tags`, `git`, `gh release list`
and the PyPI JSON API (`https://pypi.org/pypi/azure-functions-doctor/json`). The `v0.16.4` case has its
own write-up under issue #670 (`docs/release-audit/v0.16.4.md`).

## Summary

| Layer | Count |
|---|---|
| Git tags (`refs/tags/*` on the remote) | 47 |
| GitHub Releases | 22 (`v0.15.0` ... `v0.23.1` plus `v0.16.4`; none earlier) |
| PyPI versions with uploaded files | 45 |
| PyPI versions without a matching tag | 0 |

Classification of the 47 tags:

| Class | Tags | Meaning |
|---|---|---|
| Published to PyPI **and** has a GitHub Release | `v0.15.0`, `v0.16.0` - `v0.16.3`, `v0.17.0` - `v0.23.1` | complete record |
| Published to PyPI, **no** GitHub Release | `v0.1.0`, `v0.1.2` - `v0.1.11`, `v0.2.0`, `v0.3.0`, `v0.4.1`, `v0.5.0` - `v0.11.0`, `v0.13.0`, `v0.14.0`, `v0.15.1` (24 tags) | release record is recoverable from PyPI + tag; see "Proposed actions" |
| Tag only: **not** published, no Release | `v0.1.1` | development/aborted tag; source still declares `0.1.0`; PyPI has no `0.1.1` |
| GitHub Release only: **not** published | `v0.16.4` | invalid; see #670 |

So the premise "do not assume every tag was published" holds for exactly two tags (`v0.1.1`,
`v0.16.4`). Every other tag has PyPI files for the same version, and there is no version in PyPI
that lacks a tag. There is no `v0.12.0` tag and no `0.12.0` on PyPI, and `0.4.0` likewise does not
exist in either place.

The moving GitHub Action major ref (`v1`) is not a package release. No `v1` tag appears in the remote
tag list inspected (it may be maintained elsewhere, for example as a branch; not verified here), and
user-facing copy must keep treating the Action ref as independent of package versions.

## Tag identity finding: `v0.1.11` was re-created after publication

The remote `v0.1.11` is a **lightweight tag** on commit `afdf7359` ("docs: update changelog",
2025-08-30), whose source declares `0.1.11`. PyPI `0.1.11` was uploaded on **2025-06-22**, about two
months earlier. A clone that fetched the tag earlier still holds an **annotated** `v0.1.11`
(tag object `a0541808`, "Release v0.1.11", tagger date 2025-06-22) pointing at commit `67f7d2ea`,
the commit that existed at publication time; git refuses to update it (`would clobber existing tag`).
Both commits are on `main` and declare `0.1.11`, so the version/ancestry audit passes either way, but
the remote tag no longer identifies the commit that was most plausibly uploaded.

This is evidence-limited: which commit built the 2025-06-22 PyPI files cannot be proven from PyPI
metadata alone, and why the tag was re-created is not recorded. Do not move it back (that would be a
second force-update); record both commits as the audit result and treat the PyPI upload date as the
authority for the release date.

## Full table

Source version is read from the tagged commit (`__init__.py`, or a static `pyproject.toml` version for
early history). Commit dates are the committer date in the committer's timezone, so they can differ
by a day from PyPI's UTC upload date (checked: `v0.7.0`, `v0.15.0`, `v0.21.2`, `v0.22.0` are
timezone artifacts; the commit precedes the upload). `Defects` use the semantics of
`tools/audit_release_tags.py` (version mismatch / not an ancestor of `main`).

| Tag | Commit | Source version | Commit date | GitHub Release | PyPI files (first upload) | Defects |
|---|---|---|---|---|---|---|
| v0.1.0 | bd094b0 | 0.1.0 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.1 | 916ee3d | 0.1.0 | 2025-06-02 | no | no | version-mismatch |
| v0.1.2 | 4b15462 | 0.1.2 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.3 | 3df3a2e | 0.1.3 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.4 | a176577 | 0.1.4 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.5 | f5485f8 | 0.1.5 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.6 | 047381f | 0.1.6 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.7 | 1dbd7c5 | 0.1.7 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.8 | a973c03 | 0.1.8 | 2025-06-02 | no | yes, 2025-06-02 | ok |
| v0.1.9 | 95e1596 | 0.1.9 | 2025-06-03 | no | yes, 2025-06-03 | ok |
| v0.1.10 | e7b53af | 0.1.10 | 2025-06-22 | no | yes, 2025-06-22 | ok |
| v0.1.11 | afdf735 | 0.1.11 | 2025-08-30 | no | yes, 2025-06-22 | ok |
| v0.2.0 | 68a011c | 0.2.0 | 2025-08-30 | no | yes, 2025-08-30 | ok |
| v0.3.0 | 1fef498 | 0.3.0 | 2025-08-30 | no | yes, 2025-08-30 | ok |
| v0.4.1 | a9fc413 | 0.4.1 | 2025-09-03 | no | yes, 2025-09-03 | ok |
| v0.5.0 | deeb342 | 0.5.0 | 2025-09-03 | no | yes, 2025-09-03 | ok |
| v0.6.0 | ffc692f | 0.6.0 | 2025-09-05 | no | yes, 2025-09-05 | ok |
| v0.7.0 | 31e2c19 | 0.7.0 | 2025-09-06 | no | yes, 2025-09-05 | ok |
| v0.8.0 | c0cb870 | 0.8.0 | 2025-09-06 | no | yes, 2025-09-06 | ok |
| v0.9.0 | 7c01e2c | 0.9.0 | 2025-09-06 | no | yes, 2025-09-06 | ok |
| v0.10.0 | f6f40e2 | 0.10.0 | 2025-09-06 | no | yes, 2025-09-06 | ok |
| v0.11.0 | 6a122dc | 0.11.0 | 2025-09-07 | no | yes, 2025-09-07 | ok |
| v0.13.0 | d70a51b | 0.13.0 | 2025-09-19 | no | yes, 2025-09-19 | ok |
| v0.14.0 | 3490eca | 0.14.0 | 2025-09-19 | no | yes, 2025-09-19 | ok |
| v0.15.0 | f855d16 | 0.15.0 | 2026-03-09 | yes | yes, 2026-03-08 | ok |
| v0.15.1 | bbe08e5 | 0.15.1 | 2026-03-14 | no | yes, 2026-03-14 | ok |
| v0.16.0 | 06730c4 | 0.16.0 | 2026-03-15 | yes | yes, 2026-03-15 | ok |
| v0.16.1 | 9cac092 | 0.16.1 | 2026-03-21 | yes | yes, 2026-03-21 | ok |
| v0.16.2 | 2878efb | 0.16.2 | 2026-03-29 | yes | yes, 2026-03-29 | ok |
| v0.16.3 | 8766d76 | 0.16.3 | 2026-04-10 | yes | yes, 2026-04-10 | ok |
| v0.16.4 | 2e45245 | 0.16.2 | 2026-04-17 | yes | no | version-mismatch,not-on-main |
| v0.17.0 | 9f5ce2c | 0.17.0 | 2026-04-26 | yes | yes, 2026-04-26 | ok |
| v0.17.1 | f8fa1ba | 0.17.1 | 2026-05-14 | yes | yes, 2026-05-14 | ok |
| v0.17.2 | 45c5084 | 0.17.2 | 2026-07-18 | yes | yes, 2026-07-18 | ok |
| v0.18.0 | 60c9cfc | 0.18.0 | 2026-08-09 | yes | yes, 2026-08-09 | ok |
| v0.19.0 | bd94a0b | 0.19.0 | 2026-08-11 | yes | yes, 2026-08-11 | ok |
| v0.19.1 | d10b4c6 | 0.19.1 | 2026-08-12 | yes | yes, 2026-08-12 | ok |
| v0.19.2 | 59299d8 | 0.19.2 | 2026-08-14 | yes | yes, 2026-08-14 | ok |
| v0.20.0 | 6a9f2bf | 0.20.0 | 2026-09-06 | yes | yes, 2026-09-06 | ok |
| v0.21.0 | d1633bc | 0.21.0 | 2026-09-29 | yes | yes, 2026-09-29 | ok |
| v0.21.1 | 0967519 | 0.21.1 | 2026-10-02 | yes | yes, 2026-10-02 | ok |
| v0.21.2 | 3f78cec | 0.21.2 | 2026-10-03 | yes | yes, 2026-10-02 | ok |
| v0.21.3 | 5048e4c | 0.21.3 | 2026-10-04 | yes | yes, 2026-10-04 | ok |
| v0.22.0 | 94ed657 | 0.22.0 | 2026-10-07 | yes | yes, 2026-10-06 | ok |
| v0.22.1 | b79ad00 | 0.22.1 | 2026-10-07 | yes | yes, 2026-10-07 | ok |
| v0.23.0 | 697e678 | 0.23.0 | 2026-10-16 | yes | yes, 2026-10-16 | ok |
| v0.23.1 | 085cd88 | 0.23.1 | 2026-10-16 | yes | yes, 2026-10-16 | ok |

## Proposed actions (none executed; owner action)

1. **Restoring records.** For the 24 published-but-no-Release tags, creating GitHub Releases is
   optional and cosmetic. If done, create them on the **existing** tag (`gh release create <tag>
   --verify-tag`), never with a different target, mark them `--latest=false`, and generate the body
   from verified changelog/PR evidence in the layout used by `tools/release_notes.py` (#657).
   Do not create a Release for `v0.1.1`. Do not re-upload packages.
2. **`v0.1.1`.** Leave the tag; if a Release is ever added, state it is a tag-only development marker
   with no PyPI distribution. Keep its registered exception in `tools/audit_release_tags.py` (#672).
3. **`v0.1.11`.** Leave the remote tag as is; if a Release is created, note that the tag was
   re-created on 2025-08-30 and the PyPI upload date is 2025-06-22.
4. **Release notes.** Present package versions as `vX.Y.Z` and the Action ref as "Action `v1`" so the
   two are never conflated (#657).
5. The PyPI and Release columns need network access; the tag/source/ancestry columns can be re-run
   with `python tools/audit_release_tags.py --all` once #672 lands.

## Acceptance mapping (#671)

- All early tags audited and classified: yes (table above).
- Recoverable published release records have verifiable documentation: yes (table + PyPI dates);
  creating the live records is an owner action and is **not done**.
- No rewriting of tag identity or PyPI artifacts: yes (read-only).
