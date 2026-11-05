#!/bin/zsh
# Safe six-hour source refresh: stage -> validate -> publish ONLY on success.
# Use launchd; no GitHub Actions, no credentials embedded in this script.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PYTHON="${GARASU_PYTHON:-python3}"
MIHOMO="${GARASU_MIHOMO_CORE:-/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo}"
SINGBOX="${GARASU_SINGBOX_CORE:?Set GARASU_SINGBOX_CORE to the local sing-box binary}"
REPO_URL="https://github.com/togahimoko/garasu.git"
LOCK_DIR="${TMPDIR:-/tmp}/garasu-rule-refresh.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  print -r -- "SKIP: Garasu rule refresh already running"
  exit 0
fi
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/garasu-rule-refresh.XXXXXX")"
trap 'rm -rf "$WORK_DIR"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

git clone --quiet --depth 1 --single-branch --branch main "$REPO_URL" "$WORK_DIR/garasu"
cd "$WORK_DIR/garasu"

# Refresh source rules/GeoSite/GeoIP as one validated upstream snapshot.
"$PYTHON" scripts/refresh.py
# MIT upstream extra categories + official Telegram CIDRs, one pinned snapshot.
"$PYTHON" scripts/refresh_extra_categories.py --refresh
# Rebuild all format-specific remote sources and compact routing templates.
"$PYTHON" scripts/sync_universal_routing.py --write
"$PYTHON" scripts/build_binary_assets.py --mihomo-core "$MIHOMO" --singbox-core "$SINGBOX" --write
"$PYTHON" scripts/sync_public_links.py --write
# Alias synchronization can update manifest file digests; refresh QA reports.
"$PYTHON" scripts/audit_rules.py --write
"$PYTHON" scripts/audit_route_coverage.py --write
"$PYTHON" scripts/audit_geodata.py --write

# Any failed check stops before commit/push; published assets stay untouched.
"$PYTHON" scripts/qa.py --branch main --core "$MIHOMO" --singbox-core "$SINGBOX"

git add -A -- rules geo release clients install reports
if git diff --cached --quiet; then
  print -r -- "PASS: sources unchanged; binary assets match. No commit needed."
  exit 0
fi
# Reuse the repository's existing credited author, no login or token stored.
AUTHOR_NAME="$(git log -1 --format=%an)"
AUTHOR_EMAIL="$(git log -1 --format=%ae)"
git -c user.name="$AUTHOR_NAME" -c user.email="$AUTHOR_EMAIL" \
  commit -m "chore(rules): validated six-hour Garasu refresh"
# Non-fast-forward push is rejected; next execution reclones current main.
git push origin HEAD:refs/heads/main
print -r -- "PASS: validated rule assets published"
