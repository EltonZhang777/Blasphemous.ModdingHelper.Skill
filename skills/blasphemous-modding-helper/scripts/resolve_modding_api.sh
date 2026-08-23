#!/usr/bin/env bash
#
# Resolve a ModdingAPI selector to a stable reference and canonical URLs.
#
# "latest" is deliberately backed by the official GitHub Releases API. The
# default path never falls back to the repository's main branch.
#

set -euo pipefail

readonly MODDING_API_REPOSITORY="https://github.com/BrandenEK/Blasphemous.ModdingAPI.git"
readonly MODDING_API_WEB_REPOSITORY="https://github.com/BrandenEK/Blasphemous.ModdingAPI"
readonly MODDING_API_RELEASE_API="https://api.github.com/repos/BrandenEK/Blasphemous.ModdingAPI/releases/latest"

selector="latest"
metadata_file=""
metadata_json=""
metadata_tag=""
metadata_draft=""
metadata_prerelease=""
metadata_resolved_commit=""
optional_metadata_commit=""
optional_metadata_ref=""

usage() {
    cat <<'EOF'
Usage:
  resolve_modding_api.sh [--selector SELECTOR] [--metadata-file PATH]

Selectors:
  latest             Resolve the newest stable GitHub Release.
  tag:REF            Resolve an explicit Git tag.
  branch:REF         Resolve an explicit Git branch.
  commit:SHA         Resolve an exact 40-character commit.

Options:
  --metadata-file PATH
      Read Release-shaped JSON from PATH instead of the GitHub Releases API.
      This is intended for deterministic tests and offline fixture use.
  --help
EOF
}

error_report() {
    local exit_code="$1"
    local cause="$2"
    local next_step="$3"

    {
        printf '%s\n' "[ERROR REPORT]"
        printf 'operation: resolve_modding_api\n'
        printf 'selector: %s\n' "$selector"
        printf 'cause: %s\n' "$cause"
        printf 'next_step: %s\n' "$next_step"
    } >&2
    exit "$exit_code"
}

extract_json_string() {
    local key="$1"
    local json="$2"

    printf '%s\n' "$json" | sed -nE 's/.*"'$key'"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p'
}

extract_json_boolean() {
    local key="$1"
    local json="$2"

    printf '%s\n' "$json" | sed -nE 's/.*"'$key'"[[:space:]]*:[[:space:]]*(true|false).*/\1/p'
}

validate_json_document() {
    local json="$1"

    [[ "$json" == \{*\} ]] || return 1
    [[ "$json" != *,\} && "$json" != *,\] ]] || return 1
    printf '%s\n' "$json" | awk '
        BEGIN { in_string = 0; escaped = 0; depth = 0; valid = 1 }
        {
            for (i = 1; i <= length($0); i++) {
                c = substr($0, i, 1)
                if (in_string) {
                    if (escaped) {
                        escaped = 0
                    } else if (c == "\\") {
                        escaped = 1
                    } else if (c == "\"") {
                        in_string = 0
                    }
                } else if (c == "\"") {
                    in_string = 1
                } else if (c == "{" || c == "[") {
                    depth++
                } else if (c == "}" || c == "]") {
                    depth--
                    if (depth < 0) {
                        valid = 0
                    }
                }
            }
        }
        END { exit !(valid && !in_string && !escaped && depth == 0) }
    '
}

validate_ref() {
    local ref="$1"

    [[ "$ref" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || return 1
    [[ "$ref" != *..* ]] || return 1
    [[ "$ref" != */ ]] || return 1
    [[ "$ref" != *//* ]] || return 1
    [[ "$ref" != *"@{"* ]] || return 1
}

validate_commit() {
    local commit="$1"

    [[ "$commit" =~ ^[0-9a-fA-F]{40}$ ]]
}

read_metadata_file() {
    if [[ ! -f "$metadata_file" ]]; then
        error_report 2 "metadata file does not exist: $metadata_file" "Provide a readable Release metadata file or omit --metadata-file."
    fi

    if ! metadata_json="$(tr -d '\r\n' < "$metadata_file")"; then
        error_report 2 "could not read metadata file: $metadata_file" "Check the path and file permissions."
    fi
    validate_json_document "$metadata_json" || error_report 2 "metadata file is not valid JSON: $metadata_file" "Repair the JSON fixture and retry."
}

load_latest_metadata() {
    if [[ -n "$metadata_file" ]]; then
        read_metadata_file
    else
        if ! command -v curl >/dev/null 2>&1; then
            error_report 1 "curl is required to query the official GitHub Releases API" "Install curl or provide --metadata-file with a Release metadata fixture."
        fi

        if ! metadata_json="$(curl --fail --silent --show-error --location --connect-timeout 15 --max-time 60 --user-agent "blasphemous-modding-helper" "$MODDING_API_RELEASE_API" 2>/dev/null)"; then
            error_report 1 "could not retrieve the official GitHub latest Release metadata" "Check network access and retry, or provide an explicit selector."
        fi
        metadata_json="$(printf '%s' "$metadata_json" | tr -d '\r\n')"
        validate_json_document "$metadata_json" || error_report 1 "the official GitHub Release response is not valid JSON" "Retry the request or use an explicit selector."
    fi

    metadata_tag="$(extract_json_string "tag_name" "$metadata_json")"
    metadata_draft="$(extract_json_boolean "draft" "$metadata_json")"
    metadata_prerelease="$(extract_json_boolean "prerelease" "$metadata_json")"
    metadata_resolved_commit="$(extract_json_string "resolved_commit" "$metadata_json")"

    [[ -n "$metadata_tag" ]] || error_report 2 "Release metadata is missing tag_name" "Use the official Releases response or repair the fixture."
    validate_ref "$metadata_tag" || error_report 2 "Release metadata contains an invalid tag_name: $metadata_tag" "Use a valid Git reference or select an explicit tag, branch, or commit."
    [[ "$metadata_draft" == "true" || "$metadata_draft" == "false" ]] || error_report 2 "Release metadata is missing a boolean draft field" "Use the official Releases response or repair the fixture."
    [[ "$metadata_prerelease" == "true" || "$metadata_prerelease" == "false" ]] || error_report 2 "Release metadata is missing a boolean prerelease field" "Use the official Releases response or repair the fixture."
    [[ "$metadata_draft" == "false" ]] || error_report 2 "the selected latest Release is a draft" "Publish a stable Release or choose an explicit selector."
    [[ "$metadata_prerelease" == "false" ]] || error_report 2 "the selected latest Release is a prerelease" "Publish a stable Release or choose an explicit selector."

    if [[ -n "$metadata_resolved_commit" ]]; then
        validate_commit "$metadata_resolved_commit" || error_report 2 "Release metadata contains an invalid resolved_commit" "Repair the fixture or allow the resolver to query Git."
    fi
}

load_optional_metadata_commit() {
    local expected_ref="$1"

    optional_metadata_commit=""
    optional_metadata_ref=""
    [[ -n "$metadata_file" ]] || return 0

    read_metadata_file
    optional_metadata_ref="$(extract_json_string "resolved_ref" "$metadata_json")"
    optional_metadata_commit="$(extract_json_string "resolved_commit" "$metadata_json")"
    if [[ -n "$optional_metadata_commit" ]]; then
        [[ "$optional_metadata_ref" == "$expected_ref" ]] || error_report 2 "metadata resolved_ref does not match the requested reference: $expected_ref" "Repair the fixture or omit --metadata-file."
        validate_commit "$optional_metadata_commit" || error_report 2 "metadata contains an invalid resolved_commit" "Repair the fixture or omit --metadata-file."
    fi
}

resolve_remote_commit() {
    local kind="$1"
    local ref="$2"
    local remote_output=""
    local commit=""

    if ! command -v git >/dev/null 2>&1; then
        error_report 1 "git is required to resolve the explicit $kind: selector" "Install Git or use an exact commit selector."
    fi

    if [[ "$kind" == "tag" ]]; then
        if ! remote_output="$(git ls-remote --tags "$MODDING_API_REPOSITORY" "refs/tags/$ref" "refs/tags/$ref^{}" 2>/dev/null)"; then
            error_report 1 "could not query the ModdingAPI Git repository for tag $ref" "Check network access and the tag name."
        fi
        commit="$(printf '%s\n' "$remote_output" | awk -v peeled="refs/tags/$ref^{}" -v plain="refs/tags/$ref" '$2 == peeled { print $1; found = 1; exit } $2 == plain { plain_oid = $1 } END { if (!found && plain_oid != "") print plain_oid }')"
    else
        if ! remote_output="$(git ls-remote --heads "$MODDING_API_REPOSITORY" "refs/heads/$ref" 2>/dev/null)"; then
            error_report 1 "could not query the ModdingAPI Git repository for branch $ref" "Check network access and the branch name."
        fi
        commit="$(printf '%s\n' "$remote_output" | awk -v wanted="refs/heads/$ref" '$2 == wanted { print $1; exit }')"
    fi

    validate_commit "$commit" || error_report 1 "the ModdingAPI $kind $ref was not found or did not resolve to a commit" "Check the selector spelling or choose a known reference."
    resolved_commit="$commit"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --selector)
            [[ $# -ge 2 ]] || error_report 2 "--selector requires a value" "Use latest, tag:REF, branch:REF, or commit:SHA."
            selector="$2"
            shift 2
            ;;
        --metadata-file)
            [[ $# -ge 2 ]] || error_report 2 "--metadata-file requires a path" "Provide a readable JSON fixture path."
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

selector_kind=""
resolved_ref=""
resolved_tag=""
resolved_commit=""

case "$selector" in
    latest)
        selector_kind="release"
        load_latest_metadata
        resolved_tag="$metadata_tag"
        resolved_ref="$metadata_tag"
        if [[ -n "$metadata_resolved_commit" ]]; then
            resolved_commit="$metadata_resolved_commit"
        else
            resolve_remote_commit "tag" "$resolved_tag"
        fi
        ;;
    tag:*)
        selector_kind="tag"
        resolved_tag="${selector#tag:}"
        validate_ref "$resolved_tag" || error_report 2 "invalid tag selector: $selector" "Use tag:REF with a valid non-empty Git reference."
        resolved_ref="$resolved_tag"
        load_optional_metadata_commit "$resolved_tag"
        if [[ -n "$optional_metadata_commit" ]]; then
            resolved_commit="$optional_metadata_commit"
        else
            resolve_remote_commit "tag" "$resolved_tag"
        fi
        ;;
    branch:*)
        selector_kind="branch"
        branch_ref="${selector#branch:}"
        validate_ref "$branch_ref" || error_report 2 "invalid branch selector: $selector" "Use branch:REF with a valid non-empty Git reference."
        resolved_ref="$branch_ref"
        load_optional_metadata_commit "$branch_ref"
        if [[ -n "$optional_metadata_commit" ]]; then
            resolved_commit="$optional_metadata_commit"
        else
            resolve_remote_commit "branch" "$branch_ref"
        fi
        ;;
    commit:*)
        selector_kind="commit"
        resolved_commit="${selector#commit:}"
        validate_commit "$resolved_commit" || error_report 2 "invalid commit selector: $selector" "Use commit:SHA with exactly 40 hexadecimal characters."
        resolved_ref="$resolved_commit"
        ;;
    *)
        error_report 2 "invalid selector: $selector" "Use latest, tag:REF, branch:REF, or commit:SHA; main is not an implicit selector."
        ;;
esac

printf 'MODDING_API_REPOSITORY=%s\n' "$MODDING_API_REPOSITORY"
printf 'MODDING_API_SELECTOR=%s\n' "$selector"
printf 'MODDING_API_SELECTOR_KIND=%s\n' "$selector_kind"
printf 'MODDING_API_RESOLVED_REF=%s\n' "$resolved_ref"
printf 'MODDING_API_RESOLVED_TAG=%s\n' "$resolved_tag"
printf 'MODDING_API_RESOLVED_COMMIT=%s\n' "$resolved_commit"
printf 'MODDING_API_DOCS_URL=%s/tree/%s/docs\n' "$MODDING_API_WEB_REPOSITORY" "$resolved_ref"
printf 'MODDING_API_SOURCE_URL=%s/tree/%s\n' "$MODDING_API_WEB_REPOSITORY" "$resolved_ref"
