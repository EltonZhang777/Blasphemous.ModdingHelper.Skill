#!/usr/bin/env bash
# Cross-platform entry point; clone behavior lives in clone_modding_api.js.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/modding_api_shell_common.sh"
invoke_modding_api_node "$SCRIPT_DIR" "clone_modding_api.js" "$@"
