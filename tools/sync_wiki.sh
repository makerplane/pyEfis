#!/usr/bin/env bash
#
# Mirror the canonical manual (docs/wiki/) to a local clone of the GitHub wiki.
#
# This does NOT push. It clones/updates a sibling ../pyEfis.wiki working copy,
# copies the pages and images, and rewrites links/image paths for the wiki.
# Review the result and push it yourself (publishing is outward-facing).
#
# Usage:
#   tools/sync_wiki.sh [wiki-remote-url] [wiki-clone-dir]
#
# Defaults:
#   wiki-remote-url = https://github.com/billmallard/pyEfis.wiki.git
#   wiki-clone-dir  = ../pyEfis.wiki   (relative to repo root)
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/docs/wiki"
IMG="$REPO_ROOT/docs/images"
WIKI_URL="${1:-https://github.com/billmallard/pyEfis.wiki.git}"
WIKI_DIR="${2:-$REPO_ROOT/../pyEfis.wiki}"

if [ ! -d "$SRC" ]; then
  echo "error: $SRC not found" >&2
  exit 1
fi

# 1. Clone or update the wiki working copy.
if [ -d "$WIKI_DIR/.git" ]; then
  echo "Updating existing wiki clone at $WIKI_DIR"
  git -C "$WIKI_DIR" pull --ff-only
else
  echo "Cloning wiki from $WIKI_URL into $WIKI_DIR"
  echo "  (the wiki must exist: open the repo's Wiki tab and create one page first)"
  git clone "$WIKI_URL" "$WIKI_DIR"
fi

# 2. Copy images.
mkdir -p "$WIKI_DIR/images"
if [ -d "$IMG" ]; then
  cp -f "$IMG"/* "$WIKI_DIR/images/" 2>/dev/null || true
fi

# 3. Copy each page, rewriting:
#      ../images/  ->  images/      (image location in the wiki)
#      ](Page.md)  ->  ](Page)      (inter-page links without extension)
shopt -s nullglob
for f in "$SRC"/*.md; do
  base="$(basename "$f")"
  sed -e 's#\.\./images/#images/#g' \
      -e 's#\](\([A-Za-z0-9_-]*\)\.md\([)#]\)#](\1\2#g' \
      "$f" > "$WIKI_DIR/$base"
  echo "  page: $base"
done

echo
echo "Mirror staged in $WIKI_DIR (NOT pushed)."
echo "Review and publish:"
echo "  cd \"$WIKI_DIR\" && git add -A && git commit -m 'Sync manual from docs/wiki' && git push"
