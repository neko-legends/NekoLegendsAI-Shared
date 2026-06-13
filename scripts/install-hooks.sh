#!/usr/bin/env bash
# install-hooks.sh — install the Neko Legends suite pre-commit hook into sibling
# app repos. The hook runs neko_suite_doctor.py and blocks a commit if a vendored
# module drifted from canonical or two apps share an agent port.
#
# Git hooks are NOT shared via clone, so each developer/machine runs this once.
# Run it from anywhere; it locates the suite root relative to this script.
#
#   bash NekoLegendsAI-Shared/scripts/install-hooks.sh           # install into all sibling repos
#   bash NekoLegendsAI-Shared/scripts/install-hooks.sh <repo>... # install into named repos only
#
# Re-running is safe (idempotent). To remove, delete .git/hooks/pre-commit in a repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
SUITE_ROOT="$(cd "$SHARED_REPO/.." && pwd)"

# The hook body that gets written into each repo's .git/hooks/pre-commit.
# It finds the shared repo as a sibling, and SKIPS (does not block) if absent —
# so a standalone clone of one app still commits fine.
read -r -d '' HOOK_BODY <<'HOOK' || true
#!/usr/bin/env bash
# Neko Legends suite pre-commit hook (installed by NekoLegendsAI-Shared).
# Blocks the commit if a vendored module drifted or agent ports collide.
# Skips gracefully if the shared repo isn't checked out as a sibling.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SUITE_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
DOCTOR="$SUITE_ROOT/NekoLegendsAI-Shared/scripts/neko_suite_doctor.py"

if [ ! -f "$DOCTOR" ]; then
  echo "neko pre-commit: NekoLegendsAI-Shared not found as a sibling — skipping suite checks."
  exit 0
fi

PY="$(command -v python || command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "neko pre-commit: python not found — skipping suite checks."
  exit 0
fi

if ! "$PY" "$DOCTOR" --quiet; then
  echo ""
  echo "✗ neko pre-commit: suite invariant check failed (see above)."
  echo "  Fix drift automatically:  python \"$DOCTOR\" --fix"
  echo "  Then re-stage and commit. To bypass once: git commit --no-verify"
  exit 1
fi
exit 0
HOOK

install_into() {
  local repo_dir="$1"
  local name
  name="$(basename "$repo_dir")"
  if [ ! -d "$repo_dir/.git" ]; then
    echo "  skip $name (not a git repo)"
    return
  fi
  local hook_path="$repo_dir/.git/hooks/pre-commit"
  printf '%s\n' "$HOOK_BODY" > "$hook_path"
  chmod +x "$hook_path"
  echo "  ✓ installed into $name"
}

echo "Installing Neko Legends pre-commit hook"
echo "  suite root: $SUITE_ROOT"

if [ "$#" -gt 0 ]; then
  for arg in "$@"; do
    install_into "$SUITE_ROOT/$arg"
  done
else
  for dir in "$SUITE_ROOT"/*/; do
    install_into "${dir%/}"
  done
fi

echo "Done. The hook runs neko_suite_doctor.py --quiet before each commit."
