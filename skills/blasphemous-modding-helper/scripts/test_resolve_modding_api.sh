#!/usr/bin/env bash
#
# Public-behavior tests for resolve_modding_api.sh.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$SCRIPT_DIR/resolve_modding_api.sh"
FIXTURES="$SCRIPT_DIR/testdata"

fail() {
    echo "[FAIL] $*" >&2
    exit 1
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    [[ "$haystack" == *"$needle"* ]] || fail "Expected output to contain: $needle"
}

latest_output=$(bash "$RESOLVER" --selector latest --metadata-file "$FIXTURES/modding-api-release-latest.json") || {
    fail "latest selector should succeed"
}
assert_contains "$latest_output" "MODDING_API_SELECTOR=latest"
assert_contains "$latest_output" "MODDING_API_SELECTOR_KIND=release"
assert_contains "$latest_output" "MODDING_API_RESOLVED_TAG=3.0.1"
assert_contains "$latest_output" "MODDING_API_RESOLVED_COMMIT=0123456789012345678901234567890123456789"
assert_contains "$latest_output" "MODDING_API_DOCS_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/3.0.1/docs"
assert_contains "$latest_output" "MODDING_API_SOURCE_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/3.0.1"

tag_output=$(bash "$RESOLVER" --selector tag:2.5.0 --metadata-file "$FIXTURES/modding-api-selector-tag.json") || {
    fail "tag selector should succeed"
}
assert_contains "$tag_output" "MODDING_API_SELECTOR_KIND=tag"
assert_contains "$tag_output" "MODDING_API_RESOLVED_REF=2.5.0"
assert_contains "$tag_output" "MODDING_API_RESOLVED_COMMIT=1111111111111111111111111111111111111111"
assert_contains "$tag_output" "MODDING_API_DOCS_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/2.5.0/docs"

if mismatch_output=$(bash "$RESOLVER" --selector tag:2.5.0 --metadata-file "$FIXTURES/modding-api-release-latest.json" 2>&1); then
    fail "mismatched selector metadata should fail"
fi
assert_contains "$mismatch_output" "[ERROR REPORT]"
assert_contains "$mismatch_output" "resolved_ref"

branch_output=$(bash "$RESOLVER" --selector branch:main --metadata-file "$FIXTURES/modding-api-selector-branch.json") || {
    fail "branch selector should succeed"
}
assert_contains "$branch_output" "MODDING_API_SELECTOR_KIND=branch"
assert_contains "$branch_output" "MODDING_API_RESOLVED_REF=main"
assert_contains "$branch_output" "MODDING_API_RESOLVED_COMMIT=2222222222222222222222222222222222222222"
assert_contains "$branch_output" "MODDING_API_SOURCE_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main"

commit="0123456789012345678901234567890123456789"
commit_output=$(bash "$RESOLVER" --selector "commit:$commit" --metadata-file "$FIXTURES/modding-api-release-latest.json") || {
    fail "commit selector should succeed"
}
assert_contains "$commit_output" "MODDING_API_SELECTOR_KIND=commit"
assert_contains "$commit_output" "MODDING_API_RESOLVED_COMMIT=$commit"
assert_contains "$commit_output" "MODDING_API_DOCS_URL=https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/$commit/docs"

if prerelease_output=$(bash "$RESOLVER" --selector latest --metadata-file "$FIXTURES/modding-api-release-prerelease.json" 2>&1); then
    fail "prerelease metadata should fail"
fi
assert_contains "$prerelease_output" "[ERROR REPORT]"
assert_contains "$prerelease_output" "prerelease"

if draft_output=$(bash "$RESOLVER" --selector latest --metadata-file "$FIXTURES/modding-api-release-draft.json" 2>&1); then
    fail "draft metadata should fail"
fi
assert_contains "$draft_output" "[ERROR REPORT]"
assert_contains "$draft_output" "draft"

if invalid_output=$(bash "$RESOLVER" --selector main --metadata-file "$FIXTURES/modding-api-release-latest.json" 2>&1); then
    fail "invalid selector should fail"
fi
assert_contains "$invalid_output" "[ERROR REPORT]"
assert_contains "$invalid_output" "selector"

if malformed_output=$(bash "$RESOLVER" --selector latest --metadata-file "$FIXTURES/modding-api-release-malformed.json" 2>&1); then
    fail "malformed metadata should fail"
fi
assert_contains "$malformed_output" "[ERROR REPORT]"
assert_contains "$malformed_output" "tag_name"

if invalid_json_output=$(bash "$RESOLVER" --selector latest --metadata-file "$FIXTURES/modding-api-release-invalid-json.json" 2>&1); then
    fail "invalid JSON metadata should fail"
fi
assert_contains "$invalid_json_output" "[ERROR REPORT]"
assert_contains "$invalid_json_output" "JSON"

echo "[OK] resolve_modding_api.sh public behavior"
