#!/usr/bin/env bash
set -euo pipefail

# ==============================================================
# Blasphemous Modding Helper — Unix installer wrapper
# ==============================================================
# Run this script from a cloned repository. It forwards every argument
# to the adjacent bin/install.js.
#
# Usage:
#   bash install.sh --path <AGENT_SKILLS_DIR>/blasphemous-modding-helper
#   bash install.sh --path <AGENT_SKILLS_DIR>/blasphemous-modding-helper --dry-run
#   bash install.sh --path <AGENT_SKILLS_DIR>/blasphemous-modding-helper --uninstall
# ==============================================================

SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_SOURCE" ]] && command -v cygpath >/dev/null 2>&1; then
  SCRIPT_SOURCE="$(cygpath -u "$SCRIPT_SOURCE" 2>/dev/null || printf '%s' "$SCRIPT_SOURCE")"
fi

if [[ -z "$SCRIPT_SOURCE" || "${SCRIPT_SOURCE##*/}" != "install.sh" || ! -f "$SCRIPT_SOURCE" ]]; then
  echo "Error: install.sh must be run from a cloned checkout." >&2
  echo "Clone the repository, then run the local install.sh." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
LOCAL_INSTALLER="$SCRIPT_DIR/bin/install.js"
if [[ ! -f "$LOCAL_INSTALLER" ]]; then
  echo "Error: the local installer was not found at $LOCAL_INSTALLER" >&2
  echo "Clone the repository and run the local install.sh." >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Error: Node.js (>=18) required. Install from https://nodejs.org" >&2
  exit 1
fi

version=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo "0")
if [[ ! "$version" =~ ^[0-9]+$ ]] || (( version < 18 )); then
  echo "Error: Node $version too old. Need Node >=18. Upgrade: https://nodejs.org" >&2
  exit 1
fi

exec node "$LOCAL_INSTALLER" "$@"
