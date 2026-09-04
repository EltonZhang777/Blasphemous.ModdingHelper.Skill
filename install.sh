#!/usr/bin/env bash
set -euo pipefail

# ==============================================================
# Blasphemous Modding Helper — Unified Installer (Unix npx shim)
# ==============================================================
# Thin wrapper around bin/install.js (the unified Node installer).
# Every flag you'd pass to bin/install.js can be passed here.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/main/install.sh | bash
#   bash install.sh --dry-run
#   bash install.sh --only claude-code
#   bash install.sh --uninstall
#
# Why npx? A single Node.js script works across platforms without
# shell quoting bugs, keeping install.sh and install.ps1 in sync.
# ==============================================================

REPO="EltonZhang777/Blasphemous.ModdingHelper.Skill"

# --- Require Node >= 18 ---
check_node() {
  if ! command -v node &>/dev/null; then
    echo "Error: Node.js (>=18) required. Install from https://nodejs.org" >&2
    exit 1
  fi
  local version
  version=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo "0")
  if [ "$version" -lt 18 ]; then
    echo "Error: Node $version too old. Need Node >=18. Upgrade: https://nodejs.org" >&2
    exit 1
  fi
}

check_node

# --- If running from a repo clone, use the wrapper's local installer ---
# BASH_SOURCE is empty or stdin-like for `curl | bash`. Do not derive a
# directory from `$0` there: `$0` is usually `bash`, so a caller's unrelated
# `bin/install.js` could otherwise be executed.
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_SOURCE" ]] && command -v cygpath &>/dev/null; then
  SCRIPT_SOURCE="$(cygpath -u "$SCRIPT_SOURCE" 2>/dev/null || printf '%s' "$SCRIPT_SOURCE")"
fi
if [[ "$SCRIPT_SOURCE" == "install.sh" || "$SCRIPT_SOURCE" == */install.sh ]] && [[ -f "$SCRIPT_SOURCE" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
  LOCAL_INSTALLER="$SCRIPT_DIR/bin/install.js"
  if [[ -f "$LOCAL_INSTALLER" ]]; then
    exec node "$LOCAL_INSTALLER" "$@"
  fi
fi

# --- Curl-pipe path: delegate to npx ---
if ! command -v npx &>/dev/null; then
  echo "Error: npx required (ships with Node >=18). Reinstall Node.js." >&2
  exit 1
fi

exec npx -y "github:$REPO" "$@"
