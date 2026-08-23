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

if fixture_gate_output=$(MODDING_API_TEST_MODE=0 MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$TEST_ROOT/fixture-gate-reference" \
    --selector latest \
    --metadata-file "$METADATA" 2>&1); then
    fail "clone metadata fixtures should require test mode"
else
    fixture_gate_exit_code=$?
fi
[[ "$fixture_gate_exit_code" -eq 2 ]] || fail "clone metadata fixtures should return exit code 2"
assert_contains "$fixture_gate_output" "require test mode"

if invalid_scope_output=$(MODDING_API_TEST_MODE=0 bash "$CLONER" \
    --scope invalid \
    --target-path "$TEST_ROOT/invalid-scope-reference" \
    --selector latest 2>&1); then
    fail "invalid scope should fail"
else
    invalid_scope_exit_code=$?
fi
[[ "$invalid_scope_exit_code" -eq 2 ]] || fail "invalid scope should return exit code 2"
assert_contains "$invalid_scope_output" "[ERROR REPORT]"
assert_contains "$invalid_scope_output" "invalid scope"

if unknown_option_output=$(bash "$CLONER" --bogus 2>&1); then
    fail "unknown options should fail"
else
    unknown_option_exit_code=$?
fi
[[ "$unknown_option_exit_code" -eq 2 ]] || fail "unknown options should return exit code 2"
assert_contains "$unknown_option_output" "unknown option"

mkdir -p "$PROJECT/.skills/blasphemous-modding-helper"
printf 'lightweight_source_code_path: legacy-source\nmodding_profile_path: legacy-profile\n' \
    > "$PROJECT/.skills/blasphemous-modding-helper/preferences.md"

blocked_parent="$TEST_ROOT/blocked-preferences"
printf 'not a directory\n' > "$blocked_parent"
rollback_target="$TEST_ROOT/rollback-reference"
if rollback_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$rollback_target" \
    --preferences-file "$blocked_parent/preferences.md" \
    --selector latest \
    --metadata-file "$METADATA" 2>&1); then
    fail "preferences failure should fail the clone"
else
    rollback_exit_code=$?
fi
[[ "$rollback_exit_code" -eq 1 ]] || fail "preferences failure should return runtime exit code 1"
assert_contains "$rollback_output" "preferences"
[[ ! -e "$rollback_target" && ! -e "$rollback_target.lock" ]] || fail "preferences failure should roll back the new checkout and lock"

lock_only_target="$TEST_ROOT/lock-only-reference"
lock_only_path="$lock_only_target.lock"
printf 'sentinel lock' > "$lock_only_path"
if lock_only_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$lock_only_target" \
    --selector latest \
    --metadata-file "$METADATA" 2>&1); then
    fail "an existing sibling lock should be rejected"
else
    lock_only_exit_code=$?
fi
[[ "$lock_only_exit_code" -eq 2 ]] || fail "an existing sibling lock should return exit code 2"
assert_contains "$lock_only_output" "lock path already exists"
[[ "$(<"$lock_only_path")" == "sentinel lock" ]] || fail "an existing sibling lock must not be replaced"
[[ ! -e "$lock_only_target" ]] || fail "a lock-only conflict must not create a checkout"

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
lock_file="$PROJECT/.skills/blasphemous-modding-helper/references/modding-api.lock"
normalized_target="$(cd "$target" && pwd)"
normalized_lock_file="$lock_file"
if command -v cygpath >/dev/null 2>&1; then
    normalized_target="$(cygpath -w "$normalized_target")"
    normalized_lock_file="$(cygpath -w "$normalized_lock_file")"
fi

assert_contains "$output" "MODDING_API_OPERATION=clone"
assert_contains "$output" "MODDING_API_REFERENCE_PATH=$normalized_target"
assert_contains "$output" "MODDING_API_SELECTOR=latest"
assert_contains "$output" "MODDING_API_RESOLVED_TAG=v1.0.0"
assert_contains "$output" "MODDING_API_RESOLVED_COMMIT=$release_commit"
assert_contains "$output" "MODDING_API_SHALLOW=true"
assert_contains "$output" "MODDING_API_LOCK_PATH=$normalized_lock_file"
assert_contains "$(<"$lock_file")" "selector: latest"
assert_contains "$(<"$lock_file")" "resolved_tag: v1.0.0"
assert_contains "$(<"$lock_file")" "resolved_commit: $release_commit"
assert_contains "$(<"$lock_file")" "checked_at: "
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
if command -v cygpath >/dev/null 2>&1; then
    configured_normalized_target="$(cygpath -w "$configured_normalized_target")"
fi
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
if command -v cygpath >/dev/null 2>&1; then
    user_normalized_target="$(cygpath -w "$user_normalized_target")"
fi
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
assert_contains "$existing_output" "current_head:"
assert_contains "$existing_output" "worktree_state:"
assert_contains "$existing_output" "network_state:"
assert_contains "$existing_output" "next_step:"

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
