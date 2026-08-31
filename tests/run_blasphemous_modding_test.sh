#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${MSYSTEM:-}" || -n "${CYGWIN:-}" || -n "${WSL_DISTRO_NAME:-}" || -n "${WSL_INTEROP:-}" ]]; then
    printf '%s\n' 'Warning [environment]: native Bash is required; compatibility shell detected.' >&2
    exit 2
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
runner="$repo_root/tests/run_blasphemous_modding_test.py"
python3_bin="${PYTHON3:-${BLASPHEMOUS_PYTHON:-}}"

if [[ -z "$python3_bin" ]]; then
    printf '%s\n' 'Error [environment]: Python 3 path is required; set PYTHON3 or BLASPHEMOUS_PYTHON.' >&2
    exit 2
fi

if ! "$python3_bin" --version >/dev/null 2>&1; then
    printf '%s\n' 'Error [environment]: configured Python 3 executable was not found or could not run.' >&2
    exit 2
fi

exec "$python3_bin" "$runner" --python "$python3_bin" "$@"
