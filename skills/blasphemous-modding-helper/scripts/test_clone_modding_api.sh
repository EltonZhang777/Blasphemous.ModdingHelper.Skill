#!/usr/bin/env bash
#
# Public-behavior tests for clone_modding_api.sh.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLONER="$SCRIPT_DIR/clone_modding_api.sh"
RESOLVER="$SCRIPT_DIR/resolve_modding_api.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT
export MODDING_API_TEST_MODE=1

fail() {
    echo "[FAIL] $*" >&2
    exit 1
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    [[ "$haystack" == *"$needle"* ]] || fail "Expected output to contain: $needle"
}

REMOTE="$TEST_ROOT/modding-api.git"
SEED="$TEST_ROOT/seed"
PROJECT="$TEST_ROOT/project"
METADATA="$TEST_ROOT/latest.json"

git init --bare "$REMOTE" >/dev/null
git init "$SEED" >/dev/null
git -C "$SEED" config user.email "test@example.invalid"
git -C "$SEED" config user.name "ModdingAPI test"
printf 'stable\n' > "$SEED/README.md"
git -C "$SEED" add README.md
git -C "$SEED" commit -m "initial stable reference" >/dev/null
git -C "$SEED" branch -M main
git -C "$SEED" tag -a v1.0.0 -m "stable release"
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push --set-upstream origin main --tags >/dev/null

release_commit="$(git -C "$SEED" rev-parse 'refs/tags/v1.0.0^{commit}')"
git -C "$SEED" checkout -b dev >/dev/null
printf 'development\n' > "$SEED/README.md"
git -C "$SEED" commit -am "development reference" >/dev/null
git -C "$SEED" push --set-upstream origin dev >/dev/null
dev_commit="$(git -C "$SEED" rev-parse HEAD)"
git -C "$SEED" checkout main >/dev/null
printf '{"tag_name":"v1.0.0","draft":false,"prerelease":false,"resolved_ref":"v1.0.0","resolved_commit":"%s"}\n' "$release_commit" > "$METADATA"
printf '{"resolved_ref":"dev","resolved_commit":"%s"}\n' "$dev_commit" > "$TEST_ROOT/dev.json"

mkdir -p "$PROJECT/.skills/blasphemous-modding-helper"
printf 'lightweight_source_code_path: legacy-source\nmodding_profile_path: legacy-profile\n' \
    > "$PROJECT/.skills/blasphemous-modding-helper/preferences.md"

pushd "$PROJECT" >/dev/null
if ! output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --scope project \
    --selector latest \
    --metadata-file "$METADATA"); then
    popd >/dev/null
    fail "latest project clone should succeed"
fi
popd >/dev/null

target="$PROJECT/.skills/blasphemous-modding-helper/references/modding-api"
preferences="$PROJECT/.skills/blasphemous-modding-helper/preferences.md"
normalized_target="$(cd "$target" && pwd)"

assert_contains "$output" "MODDING_API_OPERATION=clone"
assert_contains "$output" "MODDING_API_REFERENCE_PATH=$normalized_target"
assert_contains "$output" "MODDING_API_SELECTOR=latest"
assert_contains "$output" "MODDING_API_RESOLVED_TAG=v1.0.0"
assert_contains "$output" "MODDING_API_RESOLVED_COMMIT=$release_commit"
assert_contains "$output" "MODDING_API_SHALLOW=true"
[[ -f "$target/.git/shallow" ]] || fail "clone should use shallow history by default"
[[ "$(git -C "$target" rev-parse HEAD)" == "$release_commit" ]] || fail "clone should resolve the release commit"
if git -C "$target" symbolic-ref --quiet --short HEAD >/dev/null; then
    fail "tag-based clone should use detached HEAD"
fi
origin_url="$(git -C "$target" config --get remote.origin.url)"
if command -v cygpath >/dev/null 2>&1; then
    origin_url="$(cygpath -u "$origin_url")"
fi
[[ "$origin_url" == "$REMOTE" ]] || fail "clone should record the upstream origin"

assert_contains "$(<"$preferences")" "lightweight_source_code_path: legacy-source"
assert_contains "$(<"$preferences")" "modding_profile_path: legacy-profile"
assert_contains "$(<"$preferences")" "modding_api_reference_path: $normalized_target"
assert_contains "$(<"$preferences")" "modding_api_reference_selector: latest"

configured_target="$TEST_ROOT/preference-reference"
configured_preferences="$TEST_ROOT/configured-preferences.md"
printf 'modding_api_reference_path: %s\nmodding_api_reference_selector: tag:v1.0.0\n' \
    "$configured_target" > "$configured_preferences"
if ! configured_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --preferences-file "$configured_preferences" \
    --metadata-file "$METADATA"); then
    fail "preferences-driven clone should succeed"
fi
configured_normalized_target="$(cd "$configured_target" && pwd)"
assert_contains "$configured_output" "MODDING_API_REFERENCE_PATH=$configured_normalized_target"
assert_contains "$configured_output" "MODDING_API_SELECTOR=tag:v1.0.0"
[[ "$(git -C "$configured_target" rev-parse HEAD)" == "$release_commit" ]] || fail "preferences selector should drive the requested tag"

USER_HOME="$TEST_ROOT/user-home"
if ! user_output=$(MODDING_API_TEST_HOME="$USER_HOME" MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --scope user \
    --selector latest \
    --metadata-file "$METADATA"); then
    fail "user-scoped clone should succeed"
fi
user_target="$USER_HOME/.skills/blasphemous-modding-helper/references/modding-api"
user_preferences="$USER_HOME/.skills/blasphemous-modding-helper/preferences.md"
user_normalized_target="$(cd "$user_target" && pwd)"
assert_contains "$user_output" "MODDING_API_REFERENCE_PATH=$user_normalized_target"
[[ -d "$user_target/.git" ]] || fail "user scope should use the approved reference path"
assert_contains "$(<"$user_preferences")" "modding_api_reference_path: $user_normalized_target"

tag_target="$TEST_ROOT/tag-reference"
if ! tag_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$tag_target" \
    --selector tag:v1.0.0 \
    --metadata-file "$METADATA"); then
    fail "explicit tag clone should succeed"
fi
assert_contains "$tag_output" "MODDING_API_SELECTOR_KIND=tag"
[[ "$(git -C "$tag_target" rev-parse HEAD)" == "$release_commit" ]] || fail "tag selector should resolve the tag commit"
if git -C "$tag_target" symbolic-ref --quiet --short HEAD >/dev/null; then
    fail "explicit tag clone should use detached HEAD"
fi

branch_target="$TEST_ROOT/branch-reference"
branch_preferences="$TEST_ROOT/branch-preferences.md"
if ! branch_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$branch_target" \
    --preferences-file "$branch_preferences" \
    --selector branch:dev \
    --metadata-file "$TEST_ROOT/dev.json"); then
    fail "explicit branch clone should succeed"
fi
assert_contains "$branch_output" "MODDING_API_SELECTOR_KIND=branch"
[[ "$(git -C "$branch_target" rev-parse HEAD)" == "$dev_commit" ]] || fail "branch selector should resolve the branch commit"
[[ "$(git -C "$branch_target" branch --show-current)" == "dev" ]] || fail "branch selector should create the requested local branch"
[[ "$(git -C "$branch_target" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')" == "origin/dev" ]] || fail "branch selector should track origin/dev"
[[ -f "$branch_target/.git/shallow" ]] || fail "branch clone should be shallow"
assert_contains "$(<"$branch_preferences")" "modding_api_reference_selector: branch:dev"

commit_target="$TEST_ROOT/commit-reference"
if ! commit_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$commit_target" \
    --selector "commit:$dev_commit"); then
    fail "explicit commit clone should succeed"
fi
assert_contains "$commit_output" "MODDING_API_SELECTOR_KIND=commit"
[[ "$(git -C "$commit_target" rev-parse HEAD)" == "$dev_commit" ]] || fail "commit selector should resolve the requested commit"
if git -C "$commit_target" symbolic-ref --quiet --short HEAD >/dev/null; then
    fail "explicit commit clone should use detached HEAD"
fi

if existing_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$tag_target" \
    --selector tag:v1.0.0 \
    --metadata-file "$METADATA" 2>&1); then
    fail "existing target should be rejected"
fi
assert_contains "$existing_output" "[ERROR REPORT]"
assert_contains "$existing_output" "already exists"

skip_preferences="$TEST_ROOT/skip-preferences.md"
printf 'lightweight_source_code_path: legacy-source\n' > "$skip_preferences"
if ! remote_output=$(bash "$RESOLVER" --selector latest --metadata-file "$METADATA"); then
    fail "skip-to-remote fallback should succeed"
fi
assert_contains "$remote_output" "MODDING_API_SELECTOR_KIND=release"
if grep -Eq '^modding_api_reference_(path|selector):' "$skip_preferences"; then
    fail "skip-to-remote should not add local reference fields"
fi

setup_doc="$SCRIPT_DIR/../references/config/first-time-setup.md"
skill_doc="$SCRIPT_DIR/../SKILL.md"
reference_doc="$SCRIPT_DIR/../references/sub-skills/referencing-modding-api.md"
assert_contains "$(<"$setup_doc")" "Skip"
assert_contains "$(<"$setup_doc")" "leave local reference fields absent"
assert_contains "$(<"$skill_doc")" "Referencing ModdingAPI"
assert_contains "$(<"$reference_doc")" "Release-aware remote fallback"

echo "[OK] clone_modding_api.sh public behavior"
