#!/usr/bin/env bash
# Cross-platform entry point; lifecycle behavior lives in manage_modding_api.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_COMMAND="${PYTHON3:-${BLASPHEMOUS_PYTHON:-python3}}"
if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
    PYTHON_COMMAND="python"
fi
if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
    printf '%s\n' '[ERROR REPORT]' \
        'operation: manage_modding_api' \
        'target_path: <unset>' \
        'selector: <unset>' \
        'current_head: <unavailable>' \
        'worktree_state: unknown' \
        'network_state: unknown' \
        'cause: Python 3.9 or newer is required' \
        'next_step: Set PYTHON3 to a Python 3.9+ executable and retry.' >&2
    exit 1
fi
exec "$PYTHON_COMMAND" "$SCRIPT_DIR/manage_modding_api.py" "$@"
