#!/usr/bin/env bash
set -euo pipefail

printf 'docs_only=false\ndocs_changed=true\nfull_required=true\n' > "$GITHUB_OUTPUT"

fail_safe() {
  exit 0
}

paths=$(mktemp)
trap 'rm -f "$paths"' EXIT

if [ "$EVENT_NAME" = "pull_request" ]; then
  if [ "$IS_FORK" = "true" ]; then
    git fetch --no-tags origin \
      "+refs/pull/$PR_NUMBER/head:refs/remotes/origin/pull/$PR_NUMBER/head" || fail_safe
    HEAD_SHA=$(git rev-parse "refs/remotes/origin/pull/$PR_NUMBER/head") || fail_safe
  else
    git fetch --no-tags origin "$BASE_SHA" "$HEAD_SHA" || fail_safe
  fi
  git merge-base "$BASE_SHA" "$HEAD_SHA" >/dev/null || fail_safe
  git diff --name-only --no-renames "$BASE_SHA...$HEAD_SHA" > "$paths" || fail_safe
else
  case "$BEFORE_SHA" in
    "" | 0000000000000000000000000000000000000000) fail_safe ;;
  esac
  git cat-file -e "$BEFORE_SHA^{commit}" || fail_safe
  git merge-base --is-ancestor "$BEFORE_SHA" "$SHA" || fail_safe
  git diff --name-only --no-renames "$BEFORE_SHA" "$SHA" > "$paths" || fail_safe
fi

classified=$(bash tools/ci_classify_changes.sh < "$paths") || fail_safe
printf '%s\n' "$classified" > "$GITHUB_OUTPUT"
