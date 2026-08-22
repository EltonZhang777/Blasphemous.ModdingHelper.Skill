#!/usr/bin/env bash
#
# Create a fresh, shallow local ModdingAPI reference checkout.
#
# Existing paths are never replaced. Update/check behavior belongs to the
# later lifecycle script; this command only creates a missing reference.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$SCRIPT_DIR/resolve_modding_api.sh"

selector=""
scope=""
target_path=""
preferences_file=""
metadata_file=""
selector_was_explicit=false
target_was_explicit=false
preferences_was_explicit=false

usage() {
    cat <<'EOF'
Usage:
  clone_modding_api.sh [options]

Options:
  --scope project|user       Use the approved project or user reference path.
  --target-path PATH         Override the reference checkout path.
  --preferences-file PATH    Write the selected path and selector to preferences.md.
  --selector SELECTOR        latest, tag:REF, branch:REF, or commit:SHA.
  --metadata-file PATH       Read resolver metadata from a deterministic fixture.
  --help                     Show this help.

If --target-path is omitted, the path is read from modding_api_reference_path
in the selected preferences file, or derived from --scope. Existing paths are
never overwritten.
EOF
}

error_report() {
    local exit_code="$1"
    local cause="$2"
    local next_step="$3"
    {
        printf '[ERROR REPORT]\n'
        printf 'operation: clone_modding_api\n'
        printf 'target_path: %s\n' "${target_path:-<unset>}"
        printf 'selector: %s\n' "${selector:-<unset>}"
        printf 'cause: %s\n' "$cause"
        printf 'next_step: %s\n' "$next_step"
    } >&2
    exit "$exit_code"
}

expand_home() {
    local value="$1"
    case "$value" in
        '~') printf '%s\n' "$HOME" ;;
        '~/'*) printf '%s/%s\n' "$HOME" "${value#~/}" ;;
        *) printf '%s\n' "$value" ;;
    esac
}

normalize_path() {
    local value
    value="$(expand_home "$1")"
    if [[ "$value" != /* ]]; then
        value="$PWD/$value"
    fi

    local parent="${value%/*}"
    local leaf="${value##*/}"
    [[ -n "$parent" ]] || parent="/"
    mkdir -p "$parent" 2>/dev/null || error_report 2 "cannot create path parent: $parent" "Check the path and permissions, then retry."
    parent="$(cd -P "$parent" && pwd)"
    printf '%s/%s\n' "$parent" "$leaf"
}

read_preference() {
    local file="$1"
    local key="$2"
    [[ -f "$file" ]] || return 0
    awk -v key="$key" '
        {
            line = $0
            sub(/\r$/, "", line)
            pattern = "^[[:space:]]*" key "[[:space:]]*:"
            if (line ~ pattern) {
                sub(pattern, "", line)
                sub(/^[[:space:]]+/, "", line)
                print line
                exit
            }
        }
    ' "$file"
}

write_preferences() {
    local file="$1"
    local reference_path="$2"
    local reference_selector="$3"
    local parent="${file%/*}"
    [[ -n "$parent" ]] || parent="."
    mkdir -p "$parent" || return 1

    local temporary
    temporary="$(mktemp "$parent/.preferences.XXXXXX")" || return 1
    if [[ -f "$file" ]]; then
        awk -v reference_path="$reference_path" -v reference_selector="$reference_selector" '
            {
                line = $0
                normalized = line
                sub(/\r$/, "", normalized)
                if (normalized ~ /^[[:space:]]*modding_api_reference_path[[:space:]]*:/) {
                    print "modding_api_reference_path: " reference_path
                    path_seen = 1
                }
                else if (normalized ~ /^[[:space:]]*modding_api_reference_selector[[:space:]]*:/) {
                    print "modding_api_reference_selector: " reference_selector
                    selector_seen = 1
                }
                else {
                    print normalized
                }
            }
            END {
                if (!path_seen) print "modding_api_reference_path: " reference_path
                if (!selector_seen) print "modding_api_reference_selector: " reference_selector
            }
        ' "$file" > "$temporary" || {
            rm -f "$temporary"
            return 1
        }
    else
        {
            printf 'modding_api_reference_path: %s\n' "$reference_path"
            printf 'modding_api_reference_selector: %s\n' "$reference_selector"
        } > "$temporary" || {
            rm -f "$temporary"
            return 1
        }
    fi

    mv "$temporary" "$file" || {
        rm -f "$temporary"
        return 1
    }
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scope)
            [[ $# -ge 2 ]] || error_report 2 "--scope requires project or user" "Use --scope project or --scope user."
            scope="$2"
            [[ "$scope" == "project" || "$scope" == "user" ]] || error_report 2 "invalid scope: $scope" "Use --scope project or --scope user."
            shift 2
            ;;
        --target-path)
            [[ $# -ge 2 ]] || error_report 2 "--target-path requires a value" "Provide a local reference directory."
            target_path="$2"
            target_was_explicit=true
            shift 2
            ;;
        --preferences-file)
            [[ $# -ge 2 ]] || error_report 2 "--preferences-file requires a path" "Provide a preferences.md path."
            preferences_file="$2"
            preferences_was_explicit=true
            shift 2
            ;;
        --selector)
            [[ $# -ge 2 ]] || error_report 2 "--selector requires a value" "Use latest, tag:REF, branch:REF, or commit:SHA."
            selector="$2"
            selector_was_explicit=true
            shift 2
            ;;
        --metadata-file)
            [[ $# -ge 2 ]] || error_report 2 "--metadata-file requires a path" "Provide a readable resolver fixture."
            metadata_file="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            error_report 2 "unknown option: $1" "Use --help to see the supported options."
            ;;
    esac
done

project_target="$PWD/.skills/blasphemous-modding-helper/references/modding-api"
project_preferences="$PWD/.skills/blasphemous-modding-helper/preferences.md"
if [[ "${MODDING_API_TEST_MODE:-}" == "1" && -n "${MODDING_API_TEST_HOME:-}" ]]; then
    home_directory="$MODDING_API_TEST_HOME"
else
    home_directory="$HOME"
fi
user_target="$home_directory/.skills/blasphemous-modding-helper/references/modding-api"
user_preferences="$home_directory/.skills/blasphemous-modding-helper/preferences.md"

if [[ -n "$scope" ]]; then
    if [[ "$scope" == "project" ]]; then
        default_target="$project_target"
        default_preferences="$project_preferences"
    else
        default_target="$user_target"
        default_preferences="$user_preferences"
    fi
    if [[ -z "$preferences_file" ]]; then
        preferences_file="$default_preferences"
    fi
else
    default_target=""
    default_preferences=""
fi

if [[ -n "$preferences_file" ]]; then
    preferences_file="$(normalize_path "$preferences_file")"
    if [[ -n "$scope" && "$preferences_was_explicit" == true ]]; then
        expected_preferences="$(normalize_path "$default_preferences")"
        [[ "$preferences_file" == "$expected_preferences" ]] || \
            error_report 2 "preferences file scope does not match --scope $scope" "Use the preferences path belonging to the selected scope."
    fi
fi

if [[ "$target_was_explicit" == false && -n "$preferences_file" ]]; then
    configured_target="$(read_preference "$preferences_file" modding_api_reference_path || true)"
    if [[ -n "$configured_target" ]]; then
        target_path="$configured_target"
    fi
fi

if [[ -z "$target_path" ]]; then
    [[ -n "$default_target" ]] || error_report 2 "no local reference path was provided" "Use --target-path, --scope, or configure modding_api_reference_path in preferences.md."
    target_path="$default_target"
fi
target_path="$(normalize_path "$target_path")"

if [[ "$selector_was_explicit" == false ]]; then
    configured_selector="$(read_preference "$preferences_file" modding_api_reference_selector || true)"
    if [[ -n "$configured_selector" ]]; then
        selector="$configured_selector"
    else
        selector="latest"
    fi
fi

command -v git >/dev/null 2>&1 || error_report 1 "git is required to create a local reference" "Install Git and retry."
[[ -f "$RESOLVER" ]] || error_report 1 "resolver script is missing: $RESOLVER" "Reinstall the skill package and retry."

resolver_args=(--selector "$selector")
if [[ -n "$metadata_file" ]]; then
    resolver_args+=(--metadata-file "$metadata_file")
fi

if ! resolver_output="$(bash "$RESOLVER" "${resolver_args[@]}" 2>&1)"; then
    printf '%s\n' "$resolver_output" >&2
    error_report 1 "selector resolution failed" "Fix the selector or network/Release metadata problem, then retry."
fi

resolver_value() {
    local key="$1"
    printf '%s\n' "$resolver_output" | awk -F= -v wanted="$key" '$1 == wanted { sub(/^[^=]*=/, ""); print; exit }'
}

repository="$(resolver_value MODDING_API_REPOSITORY)"
selector_kind="$(resolver_value MODDING_API_SELECTOR_KIND)"
resolved_ref="$(resolver_value MODDING_API_RESOLVED_REF)"
resolved_tag="$(resolver_value MODDING_API_RESOLVED_TAG)"
resolved_commit="$(resolver_value MODDING_API_RESOLVED_COMMIT)"

[[ -n "$repository" && -n "$selector_kind" && -n "$resolved_ref" && -n "$resolved_commit" ]] || \
    error_report 1 "resolver returned incomplete reference metadata" "Retry the selector resolution and inspect its error report."

# This environment variable is used only by repository-owned deterministic
# tests. Normal invocations always use the official repository returned above.
if [[ -n "${MODDING_API_TEST_REPOSITORY:-}" ]]; then
    [[ "${MODDING_API_TEST_MODE:-}" == "1" ]] || \
        error_report 2 "test repository override requires test mode" "Use the official repository or run repository-owned tests with test mode enabled."
    repository="$MODDING_API_TEST_REPOSITORY"
fi

if [[ -e "$target_path" || -L "$target_path" ]]; then
    error_report 2 "target path already exists: $target_path" "Choose a missing directory or use the later update/check workflow."
fi

target_parent="${target_path%/*}"
[[ -n "$target_parent" ]] || target_parent="/"
mkdir -p "$target_parent" || error_report 2 "cannot create target parent: $target_parent" "Check the path and permissions, then retry."

staging_path=""
cleanup_staging() {
    if [[ -n "$staging_path" && -d "$staging_path" ]]; then
        rm -rf -- "$staging_path"
    fi
}
trap cleanup_staging EXIT

staging_path="$(mktemp -d "$target_path.staging.XXXXXX")" || error_report 1 "cannot create a temporary clone directory" "Check the target path and available disk space."

run_git() {
    local output
    if ! output="$(git -C "$staging_path" "$@" 2>&1)"; then
        error_report 1 "Git operation failed: $output" "Check network access, the selector, and the target path."
    fi
}

run_git init -q
run_git remote add origin "$repository"

case "$selector_kind" in
    release|tag)
        run_git fetch --depth 1 origin "refs/tags/$resolved_ref:refs/tags/$resolved_ref"
        run_git checkout --detach "refs/tags/$resolved_ref"
        ;;
    branch)
        run_git fetch --depth 1 origin "refs/heads/$resolved_ref:refs/remotes/origin/$resolved_ref"
        run_git checkout -q -b "$resolved_ref" --track "refs/remotes/origin/$resolved_ref"
        ;;
    commit)
        run_git fetch --depth 1 origin "$resolved_commit"
        run_git checkout --detach "$resolved_commit"
        ;;
    *)
        error_report 1 "resolver returned unsupported selector kind: $selector_kind" "Use latest, tag:REF, branch:REF, or commit:SHA."
        ;;
esac

actual_commit="$(git -C "$staging_path" rev-parse HEAD)"
[[ "$actual_commit" == "$resolved_commit" ]] || \
    error_report 1 "checkout resolved to $actual_commit instead of $resolved_commit" "Retry the clone and inspect the selected Git reference."
[[ -f "$staging_path/.git/shallow" ]] || \
    error_report 1 "clone is not shallow" "Retry with a Git installation that supports shallow fetches."

if [[ "$selector_kind" == "branch" ]]; then
    upstream="$(git -C "$staging_path" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
    [[ "$upstream" == "origin/$resolved_ref" ]] || \
        error_report 1 "branch does not track origin/$resolved_ref" "Retry the fresh clone with the requested branch selector."
else
    if git -C "$staging_path" symbolic-ref --quiet --short HEAD >/dev/null 2>&1; then
        error_report 1 "fixed reference is not detached" "Retry the fresh clone with the requested tag or commit selector."
    fi
fi

mv "$staging_path" "$target_path" || error_report 1 "could not finalize the clone at $target_path" "Remove only the newly created staging directory and retry."
staging_path=""

if [[ -n "$preferences_file" ]]; then
    write_preferences "$preferences_file" "$target_path" "$selector" || \
        error_report 1 "clone succeeded but preferences could not be updated: $preferences_file" "Record the absolute path and selector in preferences.md, then retry future lookups."
fi

trap - EXIT
printf 'MODDING_API_OPERATION=clone\n'
printf 'MODDING_API_REPOSITORY=%s\n' "$repository"
printf 'MODDING_API_REFERENCE_PATH=%s\n' "$target_path"
printf 'MODDING_API_PREFERENCES_FILE=%s\n' "$preferences_file"
printf 'MODDING_API_SELECTOR=%s\n' "$selector"
printf 'MODDING_API_SELECTOR_KIND=%s\n' "$selector_kind"
printf 'MODDING_API_RESOLVED_REF=%s\n' "$resolved_ref"
printf 'MODDING_API_RESOLVED_TAG=%s\n' "$resolved_tag"
printf 'MODDING_API_RESOLVED_COMMIT=%s\n' "$resolved_commit"
printf 'MODDING_API_SHALLOW=true\n'
