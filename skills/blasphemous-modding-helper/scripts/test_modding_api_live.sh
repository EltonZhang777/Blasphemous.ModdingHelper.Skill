#!/usr/bin/env bash
# Manual live Release smoke; behavior lives in Node.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_COMMAND="${MODDING_API_NODE:-node}"
exec "$NODE_COMMAND" "$SCRIPT_DIR/test_modding_api_live.js" "$@"
