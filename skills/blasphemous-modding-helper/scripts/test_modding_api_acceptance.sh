#!/usr/bin/env bash
# Cross-platform ModdingAPI acceptance gate; behavior lives in Node.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_COMMAND="${MODDING_API_NODE:-node}"
exec "$NODE_COMMAND" "$SCRIPT_DIR/test_modding_api_acceptance.js" "$@"
