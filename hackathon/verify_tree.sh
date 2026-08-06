#!/usr/bin/env bash
# Verify the working tree against the most recent backup snapshot.
#
# Why this exists: `git status --short` collapses an untracked directory into one
# "??" line, and most of this project is untracked on purpose. A change inside
# src/adjacency/imagine_signal/ is therefore INVISIBLE to git status. This script
# compares file-by-file against the last backup so an agent edit cannot hide.
#
# Usage:
#   ./hackathon/verify_tree.sh              # compare against the newest backup
#   ./hackathon/verify_tree.sh <backup-dir> # compare against a specific one

set -uo pipefail
REPO="/Users/arunsharma/code/adjacency"
BACKUPS="/Users/arunsharma/code/adjacency-backups"
SNAP="${1:-$(ls -1d "$BACKUPS"/*/ 2>/dev/null | sort | tail -1)}"

[ -d "$SNAP" ] || { echo "no backup snapshot found in $BACKUPS"; exit 2; }
cd "$REPO" || exit 2

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
tar xzf "$SNAP/untracked.tar.gz" -C "$T" 2>/dev/null || { echo "cannot read $SNAP/untracked.tar.gz"; exit 2; }

echo "repo:     $REPO"
echo "snapshot: $(basename "$SNAP")"
echo

( cd "$T" && find . -type f | sort ) > "$T/was.txt"
git ls-files --others --exclude-standard | grep -v __pycache__ | sed 's|^|./|' | sort > "$T/now.txt"

ADDED=$(comm -13 "$T/was.txt" "$T/now.txt" | grep -v '^\./\(was\|now\)\.txt$')
REMOVED=$(comm -23 "$T/was.txt" "$T/now.txt" | grep -v '^\./\(was\|now\)\.txt$')

CHANGED=""
while IFS= read -r f; do
  case "$f" in ./was.txt|./now.txt) continue;; esac
  p="${f#./}"
  [ -f "$p" ] && [ -f "$T/$f" ] && { cmp -s "$p" "$T/$f" || CHANGED="$CHANGED$p"$'\n'; }
done < "$T/was.txt"

# ERE, not BRE. grep -E treats \( as a literal paren, which silently matches nothing.
CORE_RE='^src/adjacency/imagine_signal/(gates|decisions|contracts|canonical|receipts|mutations|ports)\.py$|^src/adjacency/(gates|contracts)\.py$'
CORE=$(printf '%s' "$CHANGED" | grep -E "$CORE_RE" || true)

echo "UNTRACKED FILES"
[ -n "$ADDED" ]   && echo "$ADDED"   | sed 's/^/  + /' || echo "  + none added"
[ -n "$REMOVED" ] && echo "$REMOVED" | sed 's/^/  - /' || echo "  - none removed"
[ -n "$CHANGED" ] && printf '%s' "$CHANGED" | sed 's/^/  ~ /' || echo "  ~ none modified"

echo
echo "TRACKED FILES"
git diff > "$T/now.patch"
if cmp -s "$T/now.patch" "$SNAP/tracked-modified.patch"; then
  echo "  identical to snapshot"
else
  echo "  DIFFERS from snapshot:"; git diff --stat | sed 's/^/    /'
fi

echo
echo "GIT WRITES (rail 1)"
echo "  HEAD:      $(git rev-parse --short HEAD)  (expected cd218dd)"
echo "  unpushed:  $(git log origin/main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')  (expected 0)"
echo "  stashes:   $(git stash list | wc -l | tr -d ' ')  (expected 0)"

echo
if [ -n "$CORE" ]; then
  echo "*** STOP. UNDELEGATABLE CORE FILES WERE MODIFIED ***"
  printf '%s\n' "$CORE" | sed 's/^/    /'
  echo
  echo "    Nothing catches a mistake in these. Review every line by hand."
  exit 1
fi
if [ -z "$ADDED$REMOVED$CHANGED" ]; then
  echo "RESULT: tree is byte-identical to the snapshot."
else
  echo "RESULT: changes present, none in the undelegatable core. Review them, then:"
  echo "  env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/pytest -m \"not e2e\" -q"
  echo "  shasum -a 256 artifacts/imagine_signal/offline_demo.json"
fi
