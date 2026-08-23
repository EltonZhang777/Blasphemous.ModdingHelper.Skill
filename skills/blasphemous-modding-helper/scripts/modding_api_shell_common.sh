#!/usr/bin/env bash

_modding_api_to_windows_path() {
    local value="$1"
    if [[ "$value" =~ ^/mnt/([A-Za-z])/(.*)$ ]]; then
        printf '%s:%s\n' "${BASH_REMATCH[1]^^}" "/${BASH_REMATCH[2]}" | sed 's#/#\\#g'
    elif [[ "$value" =~ ^/([A-Za-z])/(.*)$ ]]; then
        printf '%s:%s\n' "${BASH_REMATCH[1]^^}" "/${BASH_REMATCH[2]}" | sed 's#/#\\#g'
    else
        printf '%s\n' "$value"
    fi
}

_modding_api_error_report() {
    local operation="$1"
    local cause="$2"
    local next_step="$3"
    printf '[ERROR REPORT]\noperation: %s\ntarget_path: <unset>\nselector: <unset>\ncurrent_head: <unavailable>\nworktree_state: unknown\nnetwork_state: unknown\ncause: %s\nnext_step: %s\n' \
        "$operation" "$cause" "$next_step" >&2
}

invoke_modding_api_node() {
    local script_dir="$1"
    local core_name="$2"
    shift 2
    local operation="${core_name%.js}"
    local node_command="${MODDING_API_NODE:-node}"
    if ! "$node_command" --version >/dev/null 2>&1 && [[ -z "${MODDING_API_NODE:-}" ]] && command -v node.exe >/dev/null 2>&1; then
        node_command="node.exe"
    fi
    if ! "$node_command" --version >/dev/null 2>&1; then
        _modding_api_error_report "$operation" "Node.js 18 or newer is required" "Install Node.js 18 or newer and retry."
        return 1
    fi

    local source_script="$script_dir/$core_name"
    if [[ ! -f "$source_script" ]]; then
        _modding_api_error_report "$operation" "shared manager is missing: $source_script" "Reinstall the skill package, then retry."
        return 1
    fi
    local node_script="$source_script"
    if [[ "${node_command,,}" == *node.exe ]]; then
        node_script="$(_modding_api_to_windows_path "$node_script")"
    fi

    local node_arguments=()
    local path_argument=false
    local argument
    for argument in "$@"; do
        if [[ "$path_argument" == true ]]; then
            if [[ "${node_command,,}" == *node.exe ]]; then
                node_arguments+=("$(_modding_api_to_windows_path "$argument")")
            else
                node_arguments+=("$argument")
            fi
            path_argument=false
            continue
        fi
        node_arguments+=("$argument")
        case "$argument" in
            --target-path|--preferences-file|--metadata-file)
                path_argument=true
                ;;
        esac
    done
    if [[ "${node_command,,}" == *node.exe ]]; then
        [[ "${MODDING_API_TEST_MODE:-}" == "1" ]] && node_arguments+=("--test-mode")
        if [[ "${MODDING_API_TEST_REPOSITORY:-}" == /mnt/* || "${MODDING_API_TEST_REPOSITORY:-}" == /[A-Za-z]/* ]]; then
            node_arguments+=("--test-repository" "$(_modding_api_to_windows_path "$MODDING_API_TEST_REPOSITORY")")
        fi
        if [[ "${MODDING_API_TEST_HOME:-}" == /mnt/* || "${MODDING_API_TEST_HOME:-}" == /[A-Za-z]/* ]]; then
            node_arguments+=("--test-home" "$(_modding_api_to_windows_path "$MODDING_API_TEST_HOME")")
        fi
        if [[ "$operation" == "manage" && "${MODDING_API_TEST_NETWORK_FAILURE:-}" == "1" ]]; then
            node_arguments+=("--test-network-failure")
        fi
    fi
    exec "$node_command" "$node_script" "${node_arguments[@]}"
}
