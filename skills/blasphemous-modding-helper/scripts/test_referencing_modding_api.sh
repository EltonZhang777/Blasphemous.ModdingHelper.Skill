#!/usr/bin/env bash
#
# Public-behavior documentation smoke test for referencing ModdingAPI.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE="$SCRIPT_DIR/test_referencing_modding_api.js"

if ! command -v node >/dev/null 2>&1; then
    echo "[ERROR REPORT]" >&2
    echo "operation: test_referencing_modding_api" >&2
    echo "cause: node >= 18 is required" >&2
    echo "next_step: install Node.js 18 or newer and retry" >&2
    exit 1
fi

exec node "$CORE" "$@"
