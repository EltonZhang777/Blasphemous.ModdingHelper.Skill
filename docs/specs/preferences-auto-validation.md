# Spec: Skill config auto-validation

## Problem Statement

From the user's perspective, the Skill's saved configuration can become stale or invalid without a predictable shared check. Every operational invocation currently discovers the active configuration, but it does not record when that configuration was last validated, which Skill version performed the validation, or how often the user wants the check repeated.

The current configuration is also named `preferences.md` even though the file is a YAML configuration document consumed by Python scripts. The name is inconsistent with its role and makes the validation contract harder to express. The Skill version source is stored separately from the installed Skill directory, so an installed Skill cannot reliably compare its current version with the version recorded in the user's configuration.

These gaps create six user-visible problems: first use has no recorded validation state, a Skill upgrade may continue with stale configuration, an expired validation may be skipped, a valid configuration gives no explicit pass result, an invalid configuration does not enter the existing setup recovery flow, and the validation period cannot be configured per user.

## Solution

Rename the active configuration file to `config.yml` and make it a syntax-valid YAML document while preserving the meaning of all existing configuration fields. Add managed validation metadata and a user-controlled `check_period_days` field. The shared configuration gate discovers the project or user `config.yml`, performs a lightweight freshness decision, and invokes Python validation only when the Skill version changed, validation metadata is missing or invalid, the configured period has elapsed, or the period field itself is missing and must be initialized.

On successful validation, the gate records the current UTC validation time and Skill version. A missing period is initialized to `7` days. A positive floating-point period is rounded down and written back as an integer. A rounded period of zero or less, a non-numeric value, a non-finite value, or an unsupported type is a validation failure and enters `first-time-setup`; it is not silently replaced with `7`.

Move the canonical `version.yml` beside the installed Skill definition so the version used for comparison is distributed with the Skill. Update the existing version synchronization utility and its tests to read the new source location, and remove the old source location. Do not retain a `preferences.md` alias or perform an automatic legacy-file migration; users with the old file complete `first-time-setup` to create `config.yml`.

## User Stories

1. As a Mod developer, I want the Skill to use a clearly named `config.yml`, so that the file's purpose is obvious.
2. As an AI agent, I want the active project configuration to be discovered from the canonical project location, so that project-specific settings remain scoped to the Caller Mod repository.
3. As an AI agent, I want the active user configuration to be discovered from the canonical user location, so that settings remain reusable across Caller Mod repositories.
4. As a user with both project and user configuration, I want project scope to take precedence, so that local settings override shared defaults deterministically.
5. As a user upgrading from an older Skill release, I want the Skill to compare the recorded validation version with the installed Skill version, so that upgrades cannot silently reuse stale validation.
6. As an AI agent, I want the installed Skill to carry its own version source, so that version comparison works after the Skill is distributed without the repository checkout.
7. As a maintainer, I want one canonical version source, so that public manifests and runtime validation cannot drift.
8. As a user, I want the new configuration to be valid YAML, so that standard YAML-aware tools can inspect it.
9. As a user, I want all existing configuration fields to keep their current meaning, so that renaming the file does not change my Mod workflow.
10. As a user, I want unknown configuration fields preserved, so that future or branch-specific settings are not discarded by validation.
11. As a user, I want a first validation to run when validation metadata is absent, so that a legacy or newly created configuration becomes known-good before operational work continues.
12. As a user, I want validation to run when `last_checked_version` differs from the current Skill version, so that a Skill update gets a fresh configuration check.
13. As a user, I want validation to run when `last_checked_time` is missing or malformed, so that incomplete validation state cannot suppress a check.
14. As a user, I want validation to run when the last check is older than `check_period_days`, so that stale paths and values are detected.
15. As a user, I want the elapsed-time comparison to use a strict greater-than boundary, so that a check exactly at the configured period remains valid until the next elapsed interval.
16. As a user, I want validation skipped while the configuration remains within its period and version, so that normal Skill use does not repeatedly run Python validation.
17. As an AI agent, I want a clear skipped result, so that I can distinguish a current configuration from one that has not been checked.
18. As a user, I want the default validation period to be seven days when the field is absent, so that existing configurations have a useful safe default.
19. As a user, I want a missing `check_period_days` field added automatically after successful validation, so that the configuration records the effective policy.
20. As a user, I want a positive floating-point period rounded down to an integer, so that the stored period remains simple and deterministic.
21. As a user, I want a rounded period of zero or less to fail validation, so that an invalid or dangerously frequent policy is not silently accepted.
22. As a user, I want non-numeric, non-finite, null, collection, or otherwise unsupported period values to fail validation, so that YAML type mistakes are visible.
23. As a user, I want invalid period values to enter `first-time-setup`, so that I can correct the configuration through the established recovery flow.
24. As a user, I want a successful validation to record `last_checked_time` in UTC, so that validation age is comparable across hosts.
25. As a user, I want a successful validation to record `last_checked_version`, so that the next Skill upgrade can be detected.
26. As a user, I want only managed validation fields and necessary period normalization written automatically, so that my paths and other configuration values are not changed.
27. As a user, I want comments, unknown fields, and unrelated configuration content preserved, so that automatic validation does not rewrite my document unnecessarily.
28. As a user, I want a successful validation to report an explicit pass result, so that I know the saved configuration is usable.
29. As a user, I want the pass result to identify whether validation was first-run, version-triggered, or time-triggered, so that the reason for the check is understandable.
30. As a user, I want validation errors to identify the failing condition, so that setup recovery is actionable.
31. As an AI agent, I want validation failure to return to `first-time-setup`, so that no source, log, Modding profile, or test workflow runs with untrusted configuration.
32. As a user, I want a failed configuration left unchanged until setup succeeds, so that automatic recovery cannot destroy evidence needed to repair it.
33. As a user with an old `preferences.md`, I want the Skill to require the normal setup flow for the new file, so that there is no ambiguous precedence between old and new configuration names.
34. As a maintainer, I want ordinary scope discovery output to remain compatible, so that callers that only need project/user selection do not break when validation is added.
35. As an AI agent, I want an explicit validation mode and stable result categories, so that skipped, passed, normalized, and failed outcomes can be routed without parsing prose.
36. As a maintainer, I want every operational branch to reuse the shared validation seam, so that source analysis, log analysis, Mod testing, and Mod workflows cannot drift into different configuration rules.
37. As a maintainer, I want the Python validator to run only when freshness rules require it, so that the shared gate remains lightweight for current configurations.
38. As a maintainer, I want the version updater to read the distributed Skill version source, so that release packaging and runtime version comparison use the same value.
39. As a maintainer, I want the old version source removed, so that two competing version authorities cannot reappear.
40. As a maintainer, I want updater dry-run, SemVer rejection, manifest synchronization, and missing-source checks preserved, so that the version-source move does not weaken release safety.
41. As a maintainer, I want documentation and tests to use `config.yml` consistently, so that future agents do not reintroduce the old filename.

## Implementation Decisions

- The highest runtime seam is the existing shared configuration discovery/parser module together with the existing scope-reporting Python entry point. No source, log, Mod-test, or Modding branch owns a second validation implementation.
- The shared seam retains project-over-user precedence and selects exactly one active configuration. It does not fall back to the other scope after the selected configuration fails validation.
- The canonical configuration locations keep their current scope shape, but the filename changes from `preferences.md` to `config.yml`. The old filename is not recognized, migrated, or used as a fallback.
- `config.yml` is parsed as YAML and must represent the existing configuration as a valid mapping. Existing fields remain top-level configuration fields with their existing meanings; no new nested configuration semantics are introduced by this feature.
- Parser choice is capability-driven. The implementation first uses the Python standard library when it can correctly parse and preserve the required YAML contract. If complete YAML handling for the accepted document requires an external parser, PyYAML may be added as an explicit runtime dependency and validated by the existing Python-runtime gate; it must not be installed automatically.
- The parser must preserve unknown fields and the content of unrelated fields. Automatic writes update only managed validation fields and the normalized `check_period_days` field, without broad reserialization that changes unrelated configuration content, comments, or ordering.
- The managed validation fields are `last_checked_time` and `last_checked_version`. They are written only after all required validation succeeds.
- `last_checked_time` is stored as a UTC ISO 8601 timestamp. Missing, malformed, or future timestamps cause a validation attempt rather than allowing stale state to suppress validation.
- `last_checked_version` is compared to the exact current version string read from the distributed Skill version source. No ordering or compatibility inference is performed for this gate.
- `check_period_days` is a user-controlled configuration field measured in days. A missing field uses an effective default of `7` and is written as `7` after successful validation. A numeric floating-point value is rounded down and written as an integer only when the result is positive. A result less than or equal to zero, a non-numeric value, a non-finite value, null, a collection, or another unsupported YAML type is a validation failure.
- Freshness is due when the current Skill version differs, validation metadata is missing or invalid, `check_period_days` is missing and therefore needs initialization, or elapsed UTC time is strictly greater than the configured period. Equal elapsed time is still within the valid period.
- The agent may perform the lightweight freshness decision on each operational invocation, but it invokes the full Python configuration validation only for a due configuration. A current configuration produces a stable skipped result and does not rewrite metadata.
- A validation failure reports the specific configuration or environment reason, leaves the active configuration unchanged, enters `first-time-setup`, and blocks the downstream operational branch until setup returns success.
- A successful validation reports a stable pass result, records the current timestamp and version, and records any positive normalized period. The result identifies the trigger category where that distinction is useful to the caller.
- The existing plain scope-discovery contract remains available independently of validation. Validation output uses an explicit mode or structured result so existing scope consumers do not have to parse new prose.
- The canonical version source moves beside the installed Skill definition. The existing version synchronization utility continues to validate SemVer and synchronize public manifests, but reads only the new source location. The old source file is removed.
- The release package already packages the Skill directory as a unit, so the moved version source is included with the installed Skill without adding a second release artifact.
- All repository documentation, examples, tests, and references use `config.yml`; all repository references to the old configuration filename are removed except any deliberately historical migration note.
- The first-time setup flow writes a new valid `config.yml` and includes the validation-period field. It remains responsible for user-provided path questions and path validation; automatic validation does not change the meaning of those fields.
- This specification changes the configuration contract and documentation only. It does not modify a user's external configuration, game installation, Modding profile, source tree, logs, or generated caller data during requirements work.

## Testing Decisions

- Tests verify observable behavior at the shared CLI and configuration-module boundaries: selected scope, exit status, output/result category, validation timing, file contents, preservation of unrelated content, and setup handoff. They do not assert private helper layout.
- The primary prior art is the existing Python `unittest` and subprocess coverage for preference scope discovery and decompiler setup. New validation cases should extend that boundary rather than introduce a second test framework.
- Scope tests cover project-over-user precedence, user-only selection, missing configuration, and the absence of any old-filename fallback.
- YAML tests cover a valid configuration mapping, quoted path strings, numeric scalars, comments, unknown fields, malformed YAML, duplicate keys where the selected parser exposes them, empty documents, null documents, and unsupported top-level shapes.
- Freshness tests cover first validation, current-version mismatch, missing version metadata, missing timestamp, malformed timestamp, future timestamp, elapsed time greater than the period, elapsed time exactly equal to the period, and an in-period configuration that skips Python validation.
- Period tests cover a missing field writing `7`, a positive float being floored and stored as an integer, an integer remaining stable, a rounded value of zero failing, a rounded negative value failing, quoted numeric text failing, non-numeric values failing, non-finite values failing, null failing, and collection values failing.
- Write-safety tests verify that successful validation updates only managed fields, preserves unknown fields and unrelated field values, preserves comments/order under the chosen YAML-writing contract, and does not write any field when validation fails.
- Output tests verify stable skip, pass, normalized-pass, and failure results; the existing scope-only output remains unchanged when validation mode is not requested.
- Setup-handoff tests verify that validation failures block downstream workflows and route to `first-time-setup` with the specific error, while a successful setup produces a readable new `config.yml`.
- Version-source tests extend the existing updater subprocess tests to use the Skill-directory source, reject a missing or invalid source, accept valid SemVer including prerelease/build metadata, preserve dry-run non-mutation, update every public manifest, and prove the old source path is not consulted.
- Packaging checks verify that the moved version source is included in the Skill release archive and that no repository documentation or test still refers to the old active configuration filename.
- Documentation checks validate relative links and the shared preflight/setup/schema contract. `git diff --check` and final worktree inspection remain required.
- No real game, Modding profile, Steam installation, source checkout, or external log directory is needed for this feature's automated tests.

## Out of Scope

- Implementing the feature as part of this specification task.
- Supporting `preferences.md` as a compatibility alias, automatic migration source, or fallback.
- Changing the meaning, defaults, precedence, or validation rules of existing configuration fields except where needed to parse the renamed YAML document.
- Silently repairing invalid positive/negative/zero `check_period_days` values; values that normalize to zero or less fail and enter setup.
- Silently changing user paths, source locations, Modding profile locations, launcher values, log directories, or other user-owned configuration values.
- Running Python validation on every operational invocation when freshness rules say the active configuration is still valid.
- Adding a second configuration-validation implementation to any specialized workflow branch.
- Introducing full YAML capabilities that the actual configuration contract does not need, or adding PyYAML when the required parsing can be performed correctly without it.
- Changing the public Skill version semantics, SemVer rules, or manifest set beyond moving the canonical source path.
- Modifying game files, Modding profiles, caller Mod repositories, generated decompiled source, logs, preferences/configuration outside the active setup flow, or external user data.
- Creating a commit, push, pull request, or release as part of this specification.

## Further Notes

- The latest decision that a rounded `check_period_days` value of zero or less is a validation failure supersedes the earlier exploratory suggestion to replace such a value with `7`. Only a missing field receives the automatic default `7`.
- Existing Python runtime policy remains authoritative: if PyYAML becomes necessary, the dependency must be declared and checked by setup, never silently installed.
- The version-source move and the configuration rename are coordinated documentation/release changes, but they remain separate implementation seams so each can be tested without coupling version synchronization to configuration parsing.
