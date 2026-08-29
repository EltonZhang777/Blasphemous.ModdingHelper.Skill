# Blasphemous mod test acceptance record

This record is the evidence surface for issue #19. It separates fixture evidence, shell-entrypoint evidence, and the real-profile **Manual verification** gate. A warning is an unresolved environment or user-operated step; it is not a gameplay pass.

## Automated fixture gate

Run from the repository root:

```text
<python3> -m unittest discover -s tests -p test_blasphemous_modding_test.py
```

The fixture suite exercises the CLI through temporary projects, packages, profiles, processes, logs, and session state. It does not modify a real game profile or claim gameplay verification.

| Acceptance area | Fixture evidence |
| --- | --- |
| Project, solution-root, Debug/Release, package selection | `test_classic_solution_membership_selects_matching_solution_root`, `test_xml_solution_membership_selects_solution_root`, `test_unrelated_solutions_use_project_directory_fallback`, `test_multiple_matching_solutions_fail_explicitly`, `test_duplicate_project_membership_fails_explicitly`, `test_build_uses_matching_solution_root_for_publish`, `test_build_uses_xml_solution_root_for_publish`, `test_default_build_uses_debug_and_reports_the_package_plan`, `test_release_requires_explicit_configuration`, `test_explicit_directory_artifact_skips_build`, `test_explicit_missing_artifact_does_not_fallback_to_publish` |
| Package-root mapping and unsafe inputs | `test_default_build_deploys_the_validated_package`, `test_run_deploys_artifact_relative_to_selected_modding_root`, `test_zip_parent_traversal_is_rejected_before_profile_mutation`, `test_zip_absolute_path_is_rejected_before_profile_mutation`, `test_zip_case_collision_is_rejected_as_ambiguous`, `test_explicit_directory_symlink_is_rejected`, `test_zip_symlink_entries_are_rejected` |
| Dry-run and deployment safety | `test_dry_run_resolves_project_and_profile_without_mutation`, `test_deployment_records_backups_and_hashes_without_logs`, `test_deployment_preflight_rejects_file_parent_without_mutation`, `test_deployment_rejects_hard_linked_destination_without_mutation`, `test_deployment_failure_rolls_back_partial_copy`, `test_archive_failure_rolls_back_the_new_deployment` |
| New files, changed files, and rollback order | `test_clean_restores_overwritten_files_and_keeps_new_files`, `test_clean_protects_an_overwritten_file_changed_during_testing`, `test_clean_removes_new_files_only_after_explicit_approval`, `test_clean_protects_a_new_file_changed_during_testing_when_removal_is_approved`, `test_clean_rejects_an_older_session_until_the_newer_session_is_cleaned`, `test_repeated_runs_archive_previous_session_and_status_is_newest_first` |
| Process ownership and idempotence | `test_launch_records_live_profile_process`, `test_launch_refuses_conflicting_running_launcher`, `test_launch_does_not_report_exited_process_as_launched`, `test_stop_terminates_tracked_process_and_is_idempotent`, `test_stop_and_clean_are_idempotent_when_session_state_is_gone`, `test_stop_marks_an_already_exited_process_without_termination`, `test_stop_refuses_a_reused_pid_without_termination`, `test_clean_refuses_while_the_tracked_game_process_is_running` |
| Startup states, timeout, logs, and output bounds | `test_run_reports_launched_ready_and_mod_loaded_as_distinct_states`, `test_startup_timeout_preserves_process_and_session_for_diagnosis`, `test_timeout_rechecks_evidence_at_deadline`, `test_logs_reports_bounded_current_evidence_without_persisting_logs`, `test_logs_reports_bounded_hits_with_source_path_provenance`, `test_logs_detects_early_current_hit_outside_bounded_tail`, `test_logs_marks_same_size_content_rewrite_as_current`, `test_logs_full_output_includes_the_complete_current_log`, `test_logs_requires_current_chainloader_evidence_for_ready_and_mod_loaded`, `test_logs_recognizes_structured_moddingapi_registration_for_runtime_alias`, `test_logs_recognizes_standard_bepinex_loading_record`, `test_logs_rejects_paths_errors_and_unstructured_target_text`, `test_registration_without_current_bepinex_readiness_does_not_load_mod`, `test_target_error_before_registration_does_not_promote_to_loaded`, `test_target_error_after_registration_does_not_demote_loaded_state`, `test_logs_ignores_prelaunch_bepinex_evidence_as_stale`, `test_missing_unity_log_warns_with_preference_update_handoff`, `test_missing_bepinex_log_persists_missing_source_before_failure` |
| Unicode paths and decoding boundaries | `test_dry_run_preserves_unicode_and_space_paths_with_non_utf8_console`, `test_build_error_preserves_unicode_project_path_and_exit_category`, `test_unicode_space_paths_survive_complete_lifecycle_and_bad_log_bytes` |
| Preferences, profile preflight, shell restrictions, and exit categories | `test_project_scope_overrides_user_scope`, `test_explicit_profile_overrides_project_preference`, `test_missing_preferences_returns_profile_preference_error`, `test_missing_profile_children_are_rejected_without_creation`, `test_missing_launcher_is_rejected_without_mutation`, `test_compatibility_shell_is_rejected`, `test_stop_rejects_compatibility_shell`, `test_proton_environment_is_rejected`, `test_build_failure_returns_build_error_before_artifact_validation` |
| Agent-safe help and parser contracts | `test_root_help_contains_canonical_agent_workflow_examples`, `test_command_help_lists_only_valid_options_and_context`, `test_parser_accepts_each_command_contract`, `test_parser_rejects_misplaced_command_options` |

Completion criterion: the fixture command exits successfully, all rows above remain represented by passing tests, and skipped cases are reported with their environment reason.

Observed on 2026-08-23: the process-scoped Windows PowerShell runner passed CLI help and 62 tests; 2 symlink-related cases were skipped by host privilege conditions.

Issue #49 validation on 2026-08-28: the native PowerShell runner passed CLI help and 91 tests; the same 2 symlink-related cases were skipped by host privilege conditions.

## Agent-safe help gate

The root help must expose the canonical sequence: normal `run`, current-log `logs`, tracked `stop`, newest-first `clean`, and read-only `status`. Each subcommand help is the option authority for that command. `stop` accepts only `SESSION_ID` and optional `--force`; it does not accept context, build, log, or cleanup options. Parser tests must preserve valid invocations and reject cross-command or misplaced options.

## Shell entrypoint gate

The two runners invoke the same Python CLI and fixture suite from their native shell. They perform no deployment and launch no game:

PowerShell:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\tests\run_blasphemous_modding_test.ps1 -Python "PATH\TO\python.exe"
```

Native Bash:

```bash
PYTHON3=/path/to/python3 bash tests/run_blasphemous_modding_test.sh
```

Both runners require an explicit Python 3 executable through `-Python`, `PYTHON3`, or `BLASPHEMOUS_PYTHON`; they do not infer Python from `PATH`.

The Bash runner rejects `MSYSTEM`, `CYGWIN`, WSL, and WSL interop environments before invoking the CLI. This keeps Git Bash and WSL from being reported as native Bash.

Completion criterion: each available native shell prints its shell identity, passes CLI help, and passes the same fixture suite; unavailable shells produce a warning with the reason.

## Real-profile Manual verification gate

The agent does not run this gate automatically. Deployment changes an external profile, launch starts a game process, and gameplay actions require the player. Use a disposable non-Steam or mirror profile and obtain user direction before performing it. For issue #19, the user has deferred this gate until the three worktrees are merged.

1. Confirm `preferences.md`, the project, `modding_profile_path`, and `unity_log_dir`.
2. Run the documented `run` command with the exact project/profile paths and an explicit `--startup-timeout`.
3. Record the printed test session ID, `launched`, `ready`, or `mod_loaded` state, warnings, and current BepInEx/Unity log paths.
4. Ask the player to perform the scenario and provide a natural-language **Manual verification**: state, actions, expected behavior, observed behavior, and approximate failure time.
5. Read the current logs with `logs SESSION_ID`; use `--full` only when bounded output is insufficient.
6. Stop the tracked session, then run newest-first `clean`. Confirm overwritten files are restored and new files remain unless explicit removal was approved.

Invocation template:

The agent MUST resolve a native Python 3 interpreter as `PYTHON3` before running these commands. The agent MUST run them from the caller's Mod repository and MUST set `SKILL_ROOT` in Bash or `$SkillRoot` in PowerShell to the installed directory containing the Skill's `SKILL.md` and `scripts/`, as defined by the [authoritative command context](../../skills/blasphemous-modding-helper/SKILL.md#skill-command-context).

PowerShell:

```powershell
$PYTHON3 = 'C:\path\to\python.exe'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\blasphemous_modding_test.py') run --project <PROJECT.csproj> --profile <PROFILE> --unity-log-dir <UNITY_LOG_DIR> --startup-timeout 60
& $PYTHON3 (Join-Path $SkillRoot 'scripts\blasphemous_modding_test.py') logs <SESSION_ID>
& $PYTHON3 (Join-Path $SkillRoot 'scripts\blasphemous_modding_test.py') stop <SESSION_ID>
& $PYTHON3 (Join-Path $SkillRoot 'scripts\blasphemous_modding_test.py') clean <SESSION_ID>
```

Native Bash:

```bash
PYTHON3=/path/to/python3
"$PYTHON3" "$SKILL_ROOT/scripts/blasphemous_modding_test.py" run --project <PROJECT.csproj> --profile <PROFILE> --unity-log-dir <UNITY_LOG_DIR> --startup-timeout 60
"$PYTHON3" "$SKILL_ROOT/scripts/blasphemous_modding_test.py" logs <SESSION_ID>
"$PYTHON3" "$SKILL_ROOT/scripts/blasphemous_modding_test.py" stop <SESSION_ID>
"$PYTHON3" "$SKILL_ROOT/scripts/blasphemous_modding_test.py" clean <SESSION_ID>
```

Completion criterion: the user has supplied the Manual verification and the agent has paired it with CLI/log evidence, or the record contains a warning naming the exact blocked step. `mod_loaded` never satisfies this gate by itself.

## Current environment warnings

- **Native Bash unavailable:** the current Windows host exposes `C:\Windows\System32\bash.exe` as a WSL launcher; its invocation was denied and is not evidence for native Bash. Run the Bash runner on native Linux/macOS.
- **PowerShell policy:** direct `-File` execution was blocked by the host policy; the recorded PowerShell run used process-scoped `-ExecutionPolicy Bypass` and did not change machine or user policy.
- **Real profile gate deferred:** no external profile was deployed to or launched by this worktree. The user will perform the authorized Manual verification after the three worktrees are merged.
- **Gameplay remains manual:** the CLI and fixture suite do not control game input or verify visual, input, combat, menu, save, or other gameplay behavior.
- **Symlink privilege:** the existing suite may skip directory-symlink or hard-link cases when the host denies creation; the test output is the authoritative warning for that run.

The authoritative command and recovery contract remains in the [`/blasphemous-modding-test` sub-skill](../../skills/blasphemous-modding-helper/references/sub-skills/blasphemous-modding-test.md).
