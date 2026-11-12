# Proposed standardized notes for the 22 existing GitHub Releases

Status: **proposal only (issue #657)**. No live GitHub Release, tag, `CHANGELOG.md` or version was
edited. Live edits are an owner action.

## What this is

[`proposed-release-notes/`](proposed-release-notes/SUMMARY.txt) holds one proposed body per existing
GitHub Release (`v0.15.0` ... `v0.23.1`, 22 files). They were rendered with the repository's own tool,
unchanged, from a backup dump of the current release bodies:

```bash
# read-only: dump the current bodies, then render (no GitHub write call is made)
for t in $(gh release list -L 100 --json tagName -q '.[].tagName'); do
  gh release view "$t" --json tagName,body,publishedAt > "backup/$t.json"
done
python3 -m tools.release_notes preview --backup backup --out proposed
```

`preview` uses the layout and credit rules documented in
[Release Process](../release_process.md#release-notes-layout-and-credits) (items preserved from the
existing body, no repetitive `by @yeongseon`, external humans only, no bots, a "New Contributors"
section only when GitHub shows no earlier contribution) and refuses to render a release if a PR/commit
reference or a `protected` phrase would be lost. All 22 releases rendered without failure.

## Repository change that accompanies the proposal

`.github/release-notes.json` now carries a status annotation and a protected phrase for `v0.16.4`, so
the rendered note says it is **not a published package release** (source declares `0.16.2`, commit not
on `main`, no `0.16.4` on PyPI). The facts are from the read-only investigation tracked in #670; the
annotation only affects what the tool renders, so a later `apply` cannot drop the warning.

## Review notes for the owner

- Only `v0.21.0` credits an external human (`@rupayon123`, "New Contributors", first contribution in
  #454). This is the tool's API-derived result; spot-check it before applying.
- `v0.16.4`: the original body was only a compare link, so the tool reconstructs a short change list
  from the commits in `v0.16.3...v0.16.4` and says so. Its "Full Changelog" link therefore changes from
  `v0.16.2...v0.16.4` to `v0.16.3...v0.16.4`. Evidence is limited: the tag is not on `main`.
- `v0.23.1`: keeps the existing annotation separating the rolling Action `v1` ref from the package
  version.
- Compare links for old releases may use the former repository name; GitHub redirects the renamed
  repository, and the tool normalizes them through `legacy_repos`. Redirect behavior itself was not
  re-tested here.
- Package releases earlier than `v0.15.0` have **no** GitHub Release; see the history audit under #671.

## Applying (owner action, not done)

```bash
export GH_TOKEN=$(gh auth token)
python3 -m tools.release_notes apply v0.21.0 --dry-run          # inspect first
python3 -m tools.release_notes apply v0.21.0 --backup ./release-backup
```

This edits only the Release body; it never republishes a package or touches a tag.

## Definition-of-done status (#657)

| Item | Status |
|---|---|
| Layout, attribution policy, tooling, repeatable preview/tests | Done earlier (tooling merged); preview re-run here on all 22 releases |
| `v0.16.4` honest note | Proposed (annotation in config + rendered body); live Release not edited |
| Past 22 Releases standardized | **Not done**: proposals only, awaiting owner |
| `v0.23.1` Action-ref vs package distinction | Present in config annotation; live state not re-verified here |
