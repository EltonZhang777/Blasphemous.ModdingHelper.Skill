#!/usr/bin/env bash
#
# Public-behavior tests for manage_modding_api.sh.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLONER="$SCRIPT_DIR/clone_modding_api.sh"
MANAGER="$SCRIPT_DIR/manage_modding_api.sh"
if ! command -v node >/dev/null 2>&1 && command -v node.exe >/dev/null 2>&1; then
    TEST_ROOT="$(mktemp -d "$SCRIPT_DIR/.modding-api-lifecycle-test.XXXXXX")"
else
    TEST_ROOT="$(mktemp -d)"
fi
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

assert_error_report() {
    local text="$1"
    assert_contains "$text" "[ERROR REPORT]"
    assert_contains "$text" "operation:"
    assert_contains "$text" "target_path:"
    assert_contains "$text" "selector:"
    assert_contains "$text" "current_head:"
    assert_contains "$text" "worktree_state:"
    assert_contains "$text" "network_state:"
    assert_contains "$text" "cause:"
    assert_contains "$text" "next_step:"
}

REMOTE="$TEST_ROOT/modding-api.git"
SEED="$TEST_ROOT/seed"
TARGET="$TEST_ROOT/reference"
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
printf '{"tag_name":"v1.0.0","draft":false,"prerelease":false,"resolved_ref":"v1.0.0","resolved_commit":"%s"}\n' "$release_commit" > "$METADATA"

if ! output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$TARGET" \
    --selector latest \
    --metadata-file "$METADATA"); then
    fail "fixture clone should succeed"
fi

if ! output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --offline); then
    fail "matching offline check should succeed"
fi
assert_contains "$output" "MODDING_API_OPERATION=check"
assert_contains "$output" "MODDING_API_NETWORK=offline"
assert_contains "$output" "MODDING_API_LOCK_MATCH=true"

lock_file="$TARGET.lock"
old_head="$(git -C "$TARGET" rev-parse HEAD)"
old_lock="$(<"$lock_file")"
printf 'new stable\n' > "$SEED/README.md"
git -C "$SEED" commit -am "second stable reference" >/dev/null
git -C "$SEED" tag -a v1.1.0 -m "new stable release"
git -C "$SEED" push origin main --tags >/dev/null
new_commit="$(git -C "$SEED" rev-parse 'refs/tags/v1.1.0^{commit}')"
new_metadata="$TEST_ROOT/new-latest.json"
printf '{"tag_name":"v1.1.0","draft":false,"prerelease":false,"resolved_ref":"v1.1.0","resolved_commit":"%s"}\n' "$new_commit" > "$new_metadata"

if ! dry_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$TARGET" \
    --selector latest \
    --metadata-file "$new_metadata" \
    --dry-run); then
    fail "dry-run update should succeed"
fi
assert_contains "$dry_output" "MODDING_API_DRY_RUN=true"
assert_contains "$dry_output" "MODDING_API_CHECKOUT_CHANGED=true"
[[ "$(git -C "$TARGET" rev-parse HEAD)" == "$old_head" ]] || fail "dry-run update must not change HEAD"
[[ "$(<"$lock_file")" == "$old_lock" ]] || fail "dry-run update must not change lock state"

if ! update_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$TARGET" \
    --selector latest \
    --metadata-file "$new_metadata"); then
    fail "online update should succeed"
fi
assert_contains "$update_output" "MODDING_API_OPERATION=update"
assert_contains "$update_output" "MODDING_API_CHECKOUT_CHANGED=true"
[[ "$(git -C "$TARGET" rev-parse HEAD)" == "$new_commit" ]] || fail "update should move the fixed reference to the resolved commit"
assert_contains "$(<"$lock_file")" "resolved_tag: v1.1.0"
assert_contains "$(<"$lock_file")" "resolved_commit: $new_commit"

dry_check_lock="$(<"$lock_file")"
incomplete_dry_check_lock="$(printf '%s\n' "$dry_check_lock" | sed 's/^checked_at:.*/checked_at: /')"
printf '%s\n' "$incomplete_dry_check_lock" > "$lock_file"
if ! dry_check_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --metadata-file "$new_metadata" \
    --dry-run); then
    fail "dry-run check should succeed without writing a lock"
fi
assert_contains "$dry_check_output" "MODDING_API_LOCK_MATCH=false"
assert_contains "$dry_check_output" "MODDING_API_LOCK_UPDATED=false"
assert_contains "$dry_check_output" "MODDING_API_CHECKED_AT=<not-written>"
[[ "$(<"$lock_file")" == "$incomplete_dry_check_lock" ]] || fail "dry-run check must not change lock state"
printf '%s\n' "$dry_check_lock" > "$lock_file"

default_project="$TEST_ROOT/default-project"
default_preferences_directory="$default_project/.skills/blasphemous-modding-helper"
mkdir -p "$default_preferences_directory"
printf 'modding_api_reference_path: %s\nmodding_api_reference_selector: latest\n' "$TARGET" > "$default_preferences_directory/preferences.md"
pushd "$default_project" >/dev/null
if ! default_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" --operation check --offline); then
    popd >/dev/null
    fail "project preferences should be discovered without explicit scope or path"
fi
popd >/dev/null
default_expected_target="$TARGET"
if command -v cygpath >/dev/null 2>&1; then
    default_expected_target="$(cygpath -w "$TARGET")"
fi
assert_contains "$default_output" "MODDING_API_REFERENCE_PATH=$default_expected_target"

missing_selector_project="$TEST_ROOT/missing-selector-project"
missing_selector_preferences_directory="$missing_selector_project/.skills/blasphemous-modding-helper"
mkdir -p "$missing_selector_preferences_directory"
printf 'modding_api_reference_path: %s\n' "$TARGET" > "$missing_selector_preferences_directory/preferences.md"
selector_lock_before="$(<"$lock_file")"
selector_lock_branch="${selector_lock_before/selector: latest/selector: branch:main}"
printf '%s' "$selector_lock_branch" > "$lock_file"
pushd "$missing_selector_project" >/dev/null
if missing_selector_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" --operation check --offline 2>&1); then
    popd >/dev/null
    fail "missing preferences selector should default to latest and reject a branch lock"
else
    missing_selector_exit_code=$?
fi
popd >/dev/null
[[ "$missing_selector_exit_code" -eq 1 ]] || fail "missing preferences selector should return runtime exit code 1"
assert_contains "$missing_selector_output" "requested selector latest"
printf '%s' "$selector_lock_before" > "$lock_file"

user_default_project="$TEST_ROOT/user-default-project"
user_default_home="$TEST_ROOT/user-default-home"
user_default_preferences_directory="$user_default_home/.skills/blasphemous-modding-helper"
mkdir -p "$user_default_project" "$user_default_preferences_directory"
printf 'modding_api_reference_path: %s\nmodding_api_reference_selector: latest\n' "$TARGET" > "$user_default_preferences_directory/preferences.md"
pushd "$user_default_project" >/dev/null
if ! user_default_output=$(MODDING_API_TEST_HOME="$user_default_home" MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --offline); then
    popd >/dev/null
    fail "user preferences should be discovered when project preferences are absent"
fi
popd >/dev/null
assert_contains "$user_default_output" "MODDING_API_LOCK_MATCH=true"

shape_head="$(git -C "$TARGET" rev-parse HEAD)"
shape_lock="$(<"$lock_file")"
git -C "$TARGET" checkout -b wrong-shape >/dev/null
if shape_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --offline 2>&1); then
    fail "wrong fixed-reference checkout shape should fail"
else
    shape_exit_code=$?
fi
[[ "$shape_exit_code" -eq 1 ]] || fail "wrong checkout shape should return runtime exit code 1"
assert_error_report "$shape_output"
assert_contains "$shape_output" "fixed selector requires detached HEAD"
[[ "$(git -C "$TARGET" rev-parse HEAD)" == "$shape_head" ]] || fail "wrong checkout shape must preserve HEAD"
[[ "$(<"$lock_file")" == "$shape_lock" ]] || fail "wrong checkout shape must preserve lock state"
git -C "$TARGET" checkout --detach HEAD >/dev/null

if usage_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" --operation invalid 2>&1); then
    fail "invalid operation should fail"
else
    usage_exit_code=$?
fi
[[ "$usage_exit_code" -eq 2 ]] || fail "invalid operation should return usage/configuration exit code 2"
assert_error_report "$usage_output"

printf 'local edit\n' > "$TARGET/README.md"
if dirty_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$TARGET" \
    --selector latest \
    --metadata-file "$new_metadata" 2>&1); then
    fail "dirty worktree should block update"
else
    dirty_exit_code=$?
fi
[[ "$dirty_exit_code" -eq 1 ]] || fail "dirty worktree should return runtime exit code 1"
assert_error_report "$dirty_output"
assert_contains "$dirty_output" "worktree_state: dirty"
git -C "$TARGET" checkout -- README.md

WRONG_REMOTE="$TEST_ROOT/wrong-origin.git"
git init --bare "$WRONG_REMOTE" >/dev/null
git -C "$TARGET" remote set-url origin "$WRONG_REMOTE"
if wrong_origin_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --offline 2>&1); then
    fail "wrong origin should block offline check"
else
    wrong_origin_exit_code=$?
fi
[[ "$wrong_origin_exit_code" -eq 1 ]] || fail "wrong origin should return runtime exit code 1"
assert_error_report "$wrong_origin_output"
git -C "$TARGET" remote set-url origin "$REMOTE"

valid_lock="$(<"$lock_file")"
bad_lock="${valid_lock//resolved_commit: $new_commit/resolved_commit: $old_head}"
printf '%s\n' "$bad_lock" > "$lock_file"
if mismatch_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --offline 2>&1); then
    fail "mismatching offline lock should fail"
else
    mismatch_exit_code=$?
fi
[[ "$mismatch_exit_code" -eq 1 ]] || fail "mismatching offline lock should return runtime exit code 1"
assert_error_report "$mismatch_output"
assert_contains "$mismatch_output" "does not match locked commit"
printf '%s\n' "$valid_lock" > "$lock_file"

tag_target="$TEST_ROOT/tag-reference"
if ! tag_clone_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$tag_target" \
    --selector tag:v1.0.0 \
    --metadata-file "$METADATA"); then
    fail "tag fixture clone should succeed"
fi
if ! tag_check_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$tag_target" \
    --selector tag:v1.0.0 \
    --metadata-file "$METADATA"); then
    fail "tag check should succeed"
fi
assert_contains "$tag_check_output" "MODDING_API_SELECTOR_KIND=tag"

commit_target="$TEST_ROOT/commit-reference"
if ! commit_clone_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$commit_target" \
    --selector "commit:$old_head"); then
    fail "commit fixture clone should succeed"
fi
if ! commit_check_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$commit_target" \
    --selector "commit:$old_head"); then
    fail "commit check should succeed"
fi
assert_contains "$commit_check_output" "MODDING_API_SELECTOR_KIND=commit"

commit_mismatch_lock="$(<"$commit_target.lock")"
commit_mismatch_lock="${commit_mismatch_lock//selector: commit:$old_head/selector: commit:$new_commit}"
printf '%s\n' "$commit_mismatch_lock" > "$commit_target.lock"
if commit_mismatch_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$commit_target" \
    --selector "commit:$new_commit" \
    --offline 2>&1); then
    fail "commit lock with a different resolved SHA should fail"
else
    commit_mismatch_exit_code=$?
fi
[[ "$commit_mismatch_exit_code" -eq 1 ]] || fail "commit lock mismatch should return runtime exit code 1"
assert_contains "$commit_mismatch_output" "does not match the commit selector"
commit_lock_text="$(<"$commit_target.lock")"
commit_lock_text="${commit_lock_text//selector: commit:$new_commit/selector: commit:$old_head}"
printf '%s\n' "$commit_lock_text" > "$commit_target.lock"

sed 's/^checked_at:.*/checked_at: /' "$lock_file" > "$lock_file.incomplete"
mv "$lock_file.incomplete" "$lock_file"
if ! relock_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --metadata-file "$new_metadata"); then
    fail "check should rebuild an incomplete lock"
fi
assert_contains "$relock_output" "MODDING_API_LOCK_UPDATED=true"
grep -Eq '^checked_at: .+' "$lock_file" || fail "check should restore checked_at"

if ! fallback_output=$(MODDING_API_TEST_NETWORK_FAILURE=1 MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest); then
    fail "network-failed check should use a matching lock"
fi
assert_contains "$fallback_output" "MODDING_API_NETWORK=offline"
assert_contains "$fallback_output" "MODDING_API_LOCK_MATCH=true"

network_missing_lock="$lock_file.network-missing"
mv "$lock_file" "$network_missing_lock"
if network_missing_output=$(MODDING_API_TEST_NETWORK_FAILURE=1 MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest 2>&1); then
    fail "network-failed check without a lock should fail"
else
    network_missing_exit_code=$?
fi
[[ "$network_missing_exit_code" -eq 1 ]] || fail "network-failed check without a lock should return runtime exit code 1"
assert_error_report "$network_missing_output"
assert_contains "$network_missing_output" "network_state: offline"
mv "$network_missing_lock" "$lock_file"

network_mismatch_lock="$(<"$lock_file")"
network_mismatch_lock="${network_mismatch_lock//resolved_commit: $new_commit/resolved_commit: $old_head}"
printf '%s\n' "$network_mismatch_lock" > "$lock_file"
if network_mismatch_output=$(MODDING_API_TEST_NETWORK_FAILURE=1 MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest 2>&1); then
    fail "network-failed check with a mismatching lock should fail"
else
    network_mismatch_exit_code=$?
fi
[[ "$network_mismatch_exit_code" -eq 1 ]] || fail "network-failed check with a mismatching lock should return runtime exit code 1"
assert_error_report "$network_mismatch_output"
assert_contains "$network_mismatch_output" "network_state: offline"
printf '%s\n' "$valid_lock" > "$lock_file"

missing_tag_metadata="$TEST_ROOT/missing-tag.json"
printf '{"resolved_ref":"missing-tag","resolved_commit":"%s"}\n' "0000000000000000000000000000000000000000" > "$missing_tag_metadata"
if missing_tag_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$tag_target" \
    --selector tag:missing-tag \
    --metadata-file "$missing_tag_metadata" 2>&1); then
    fail "missing tag should fail"
else
    missing_tag_exit_code=$?
fi
[[ "$missing_tag_exit_code" -eq 1 ]] || fail "missing tag should return runtime exit code 1"
assert_error_report "$missing_tag_output"

if offline_update_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$TARGET" \
    --selector latest \
    --offline 2>&1); then
    fail "offline update should fail rather than claim a refresh"
else
    offline_update_exit_code=$?
fi
[[ "$offline_update_exit_code" -eq 1 ]] || fail "offline update should return runtime exit code 1"
assert_error_report "$offline_update_output"
assert_contains "$offline_update_output" "cannot refresh a reference while offline"

saved_lock="$lock_file.saved"
mv "$lock_file" "$saved_lock"
if missing_lock_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --offline 2>&1); then
    fail "offline check without a lock should fail"
else
    missing_lock_exit_code=$?
fi
[[ "$missing_lock_exit_code" -eq 1 ]] || fail "offline check without a lock should return runtime exit code 1"
assert_error_report "$missing_lock_output"
mv "$saved_lock" "$lock_file"

missing_tag_field_lock="$(<"$lock_file")"
missing_tag_field_lock="$(printf '%s\n' "$missing_tag_field_lock" | sed '/^resolved_tag:/d')"
printf '%s\n' "$missing_tag_field_lock" > "$lock_file"
if missing_tag_field_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$TARGET" \
    --selector latest \
    --offline 2>&1); then
    fail "lock without resolved_tag should fail"
else
    missing_tag_field_exit_code=$?
fi
[[ "$missing_tag_field_exit_code" -eq 1 ]] || fail "lock without resolved_tag should return runtime exit code 1"
assert_contains "$missing_tag_field_output" "lock state is incomplete"
printf '%s\n' "$valid_lock" > "$lock_file"

invalid_target="$TEST_ROOT/invalid-reference"
mkdir -p "$invalid_target"
printf 'not git\n' > "$invalid_target/README.md"
if invalid_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation check \
    --target-path "$invalid_target" \
    --selector latest \
    --offline 2>&1); then
    fail "non-Git target should fail"
else
    invalid_exit_code=$?
fi
[[ "$invalid_exit_code" -eq 1 ]] || fail "non-Git target should return runtime exit code 1"
assert_error_report "$invalid_output"
assert_contains "$invalid_output" "not a Git worktree"

missing_commit="0000000000000000000000000000000000000000"
if missing_ref_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$TARGET" \
    --selector "commit:$missing_commit" 2>&1); then
    fail "missing commit should fail"
else
    missing_ref_exit_code=$?
fi
[[ "$missing_ref_exit_code" -eq 1 ]] || fail "missing commit should return runtime exit code 1"
assert_error_report "$missing_ref_output"

git -C "$SEED" checkout -b dev >/dev/null
printf 'dev one\n' > "$SEED/README.md"
git -C "$SEED" commit -am "first dev reference" >/dev/null
git -C "$SEED" push --set-upstream origin dev >/dev/null
dev_commit1="$(git -C "$SEED" rev-parse HEAD)"
dev_metadata="$TEST_ROOT/dev.json"
printf '{"resolved_ref":"dev","resolved_commit":"%s"}\n' "$dev_commit1" > "$dev_metadata"
branch_target="$TEST_ROOT/branch-reference"
if ! branch_clone_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$branch_target" \
    --selector branch:dev \
    --metadata-file "$dev_metadata"); then
    fail "branch fixture clone should succeed"
fi

branch_dry_head="$(git -C "$branch_target" rev-parse HEAD)"
branch_dry_lock="$(<"$branch_target.lock")"
git -C "$branch_target" update-ref -d refs/remotes/origin/dev
if ! branch_dry_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$branch_target" \
    --selector branch:dev \
    --metadata-file "$dev_metadata" \
    --dry-run); then
    fail "branch dry-run should plan a fetch when the remote-tracking ref is absent"
fi
assert_contains "$branch_dry_output" "MODDING_API_PLAN_REQUIRES_FETCH=true"
[[ "$(git -C "$branch_target" rev-parse HEAD)" == "$branch_dry_head" ]] || fail "branch dry-run must preserve HEAD"
[[ "$(<"$branch_target.lock")" == "$branch_dry_lock" ]] || fail "branch dry-run must preserve lock state"
git -C "$branch_target" update-ref refs/remotes/origin/dev "$branch_dry_head"

printf 'dev two\n' > "$SEED/README.md"
git -C "$SEED" commit -am "second dev reference" >/dev/null
git -C "$SEED" push origin dev >/dev/null
dev_commit2="$(git -C "$SEED" rev-parse HEAD)"
printf '{"resolved_ref":"dev","resolved_commit":"%s"}\n' "$dev_commit2" > "$dev_metadata"
if ! branch_update_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$branch_target" \
    --selector branch:dev \
    --metadata-file "$dev_metadata"); then
    fail "clean branch fast-forward should succeed"
fi
[[ "$(git -C "$branch_target" rev-parse HEAD)" == "$dev_commit2" ]] || fail "branch update should fast-forward to the resolved commit"

printf 'local branch\n' > "$branch_target/README.md"
git -C "$branch_target" commit -am "local divergent reference" >/dev/null
local_branch_commit="$(git -C "$branch_target" rev-parse HEAD)"
printf 'dev three\n' > "$SEED/README.md"
git -C "$SEED" commit -am "third dev reference" >/dev/null
git -C "$SEED" push origin dev >/dev/null
dev_commit3="$(git -C "$SEED" rev-parse HEAD)"
printf '{"resolved_ref":"dev","resolved_commit":"%s"}\n' "$dev_commit3" > "$dev_metadata"
branch_lock="$branch_target.lock"
branch_lock_before="$(<"$branch_lock")"
if divergent_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$branch_target" \
    --selector branch:dev \
    --metadata-file "$dev_metadata" 2>&1); then
    fail "divergent branch history should block update"
else
    divergent_exit_code=$?
fi
[[ "$divergent_exit_code" -eq 1 ]] || fail "divergent branch update should return runtime exit code 1"
assert_error_report "$divergent_output"
assert_contains "$divergent_output" "divergent"
[[ "$(git -C "$branch_target" rev-parse HEAD)" == "$local_branch_commit" ]] || fail "divergent update must preserve local branch HEAD"
[[ "$(<"$branch_lock")" == "$branch_lock_before" ]] || fail "divergent update must preserve lock state"

missing_branch_metadata="$TEST_ROOT/missing-branch.json"
printf '{"resolved_ref":"dev","resolved_commit":"%s"}\n' "0000000000000000000000000000000000000000" > "$missing_branch_metadata"
if missing_branch_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$branch_target" \
    --selector branch:dev \
    --metadata-file "$missing_branch_metadata" 2>&1); then
    fail "mismatching branch ref should fail"
else
    missing_branch_exit_code=$?
fi
[[ "$missing_branch_exit_code" -eq 1 ]] || fail "mismatching branch ref should return runtime exit code 1"
assert_error_report "$missing_branch_output"

missing_remote_target="$TEST_ROOT/missing-remote-branch-reference"
if ! missing_remote_clone_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$CLONER" \
    --target-path "$missing_remote_target" \
    --selector branch:dev \
    --metadata-file "$dev_metadata"); then
    fail "missing remote branch fixture clone should succeed"
fi
missing_remote_head="$(git -C "$missing_remote_target" rev-parse HEAD)"
git -C "$missing_remote_target" branch -m missing-branch
git -C "$missing_remote_target" update-ref refs/remotes/origin/missing-branch "$missing_remote_head"
git -C "$missing_remote_target" config branch.missing-branch.remote origin
git -C "$missing_remote_target" config branch.missing-branch.merge refs/heads/missing-branch
missing_remote_metadata="$TEST_ROOT/missing-remote-branch.json"
printf '{"resolved_ref":"missing-branch","resolved_commit":"%s"}\n' "$missing_remote_head" > "$missing_remote_metadata"
missing_remote_lock="$missing_remote_target.lock"
missing_remote_lock_before="$(<"$missing_remote_lock")"
if missing_remote_output=$(MODDING_API_TEST_REPOSITORY="$REMOTE" bash "$MANAGER" \
    --operation update \
    --target-path "$missing_remote_target" \
    --selector branch:missing-branch \
    --metadata-file "$missing_remote_metadata" 2>&1); then
    fail "missing remote branch should fail"
else
    missing_remote_exit_code=$?
fi
[[ "$missing_remote_exit_code" -eq 1 ]] || fail "missing remote branch should return runtime exit code 1"
assert_error_report "$missing_remote_output"
assert_contains "$missing_remote_output" "Git operation failed"
[[ "$(git -C "$missing_remote_target" rev-parse HEAD)" == "$missing_remote_head" ]] || fail "missing remote branch must preserve HEAD"
[[ "$(<"$missing_remote_lock")" == "$missing_remote_lock_before" ]] || fail "missing remote branch must preserve lock state"

echo "[OK] manage_modding_api.sh public behavior"
