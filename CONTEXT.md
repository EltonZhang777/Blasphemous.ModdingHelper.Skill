# Blasphemous Modding Helper Context

This context defines the vocabulary used by the skill when it generates or changes Blasphemous Mod code, builds and tests a mod, and separates caller-owned code from game, dependency, and generated content.

## Ownership and scope

**Caller Mod repository**:
The root repository in which the user is developing a Mod. It is the codebase being changed by the requested Mod task.
_Avoid_: skill repository, game installation, upstream repository

**Mod-owned code**:
C# and related source that the caller's Mod author can maintain and change.
_Avoid_: decompiled source, upstream code, dependency code, generated output

**Direct copy**:
External code reproduced without substantive behavioral or structural changes.
_Avoid_: adapted code, rewritten code

## Package and profile

**Publish directory**:
The build output container produced by a mod project. It can contain one or more package roots and release archives.
_Avoid_: build folder, latest output

**Package root**:
The directory that contains the complete deployable contents of one mod package, including plugins, data, localization, and other resource files.
_Avoid_: DLL folder, package container

**Steam game installation**:
A Blasphemous installation used as the source-acquisition input for Steam validation and DLL decompilation. It is separate from the `Modding profile` used for mod runtime testing.
_Avoid_: Modding profile, Steam install (when naming a source-acquisition path)

**Modding profile**:
A game installation or mirror prepared for mod development, identified by its game launcher, Modding directory, and BepInEx installation.
_Avoid_: Steam install, game folder (when the modded profile is meant)

**Modding root**:
The Modding directory inside the selected modding profile. Package-relative files are deployed under this directory.
_Avoid_: mod folder (when the target must be precise)

**Plugin root**:
The plugins directory inside the modding root. A package's plugin files are mapped here without changing their package-relative names.
_Avoid_: DLL folder

## Skill configuration vocabulary

**Skill configuration**:
The YAML mapping stored as `config.yml` in project or user scope; it contains caller-owned paths and optional Skill settings selected by the shared configuration gate.
_Avoid_: `preferences.md`, caller Mod source, generated runtime state

**Configuration validation metadata**:
The managed `last_checked_time` and `last_checked_version` values recording the most recent successful Skill configuration validation.
_Avoid_: user-owned path configuration, a successful Mod test

**Configuration validation period**:
The user-controlled `check_period_days` value that determines how long a successful configuration validation remains current.
_Avoid_: a Skill release lifetime, a Test session

**Skill version source**:
The canonical `version.yml` distributed beside the installed Skill definition and used for exact version comparison and manifest synchronization.
_Avoid_: a caller Mod version, a ModdingAPI release selector

## Blasphemous localization

**Blasphemous 1 localization corpus**:
A localized game-text corpus for Blasphemous 1. Blasphemous 2 remains outside this context.
_Avoid_: Blasphemous localization in general, Blasphemous 2 terms

**Localization record**:
A translation key, language, and value from the Blasphemous 1 localization corpus.
_Avoid_: canonical game concept, glossary entry

**Translation variant**:
A localized wording that represents a concept in a particular language or UI context.
_Avoid_: canonical game concept

**Code identifier**:
A name in decompiled game or Mod source that may refer to a canonical game concept.
_Avoid_: translation key, official localized name

**Localization evidence**:
Evidence for a game's wording, labels, translated names, and textual descriptions.
_Avoid_: runtime behavior evidence

**Gameplay evidence**:
Evidence for runtime behavior, mechanics, values, and code relationships from game or Mod source.
_Avoid_: translation evidence

**Canonical game concept**:
A semantic game object, resource, character, place, or mechanic supported by localization records, source-code identifiers, or aliases.
_Avoid_: translation value, localization key

**Community alias**:
A user or community expression for a canonical game concept.
_Avoid_: official translation, global synonym

**Fervour (`FERVOR`)**:
The in-game resource represented by the game's `FERVOR` localization terms.
_Avoid_: treating a community alias as its official name

**Guilt Fragment**:
The guilt drop and recovery object associated with the Penitent One's death.
_Avoid_: corpse, generic body

## Standards routing vocabulary

**Coding-standards sub-skill**:
The routing entry that applies the Mod-owned scope gate and selects the detailed standards needed for a Mod-owned C# task.
_Avoid_: legacy aggregate standards document

**Branch reference**:
A detailed standards reference selected by the Coding-standards sub-skill for one responsibility: C# and runtime Unity, ModdingAPI, or Harmony patching.
_Avoid_: competing standards authority

**Progressive disclosure**:
The routing policy that keeps shared entry rules in the Coding-standards sub-skill and loads only the Branch references triggered by the task.

**C# and runtime Unity standards**:
The Branch reference for C# naming, organization, compiler compatibility, and runtime Unity callbacks.

**ModdingAPI standards**:
The Branch reference for ModdingAPI APIs, the BlasMod lifecycle, services, development-document routing, and ModLog.

**Harmony patching standards**:
The Branch reference for Patch files and classes, targets, injections, framework-managed patch discovery, and approved manual patching.

## Project architecture vocabulary

**Project architecture guidelines**:
A soft routing guide for locating newly authored Mod-owned files and directories when a Caller Mod repository lacks an established architecture or the user asks for organization.
_Avoid_: mandatory migration, repository-wide rewrite

**Established architecture**:
Stable directory, namespace, and module boundaries already used by a Caller Mod repository; new work preserves these boundaries.
_Avoid_: a single existing folder, the Skill repository layout

**Architecture category**:
A directory whose name states the primary responsibility of its new files; each file is assigned to one primary category.
_Avoid_: catch-all directory, duplicate placement

**Components directory**:
The `Components/` category for reusable Mod-owned runtime or domain objects, state, registries, and management components.
_Avoid_: unknown files, generic utilities

**Configs directory**:
The `Configs/` category for user configuration, serialized settings, and persistence data models.
_Avoid_: live runtime components

**Extensions directory**:
The `Extensions/` category for extension methods and support types tightly coupled to those extensions.
_Avoid_: generic utility directory, legacy helper examples as authority

**Patches directory**:
The `Patches/` category for Harmony Patch files and classes; a Harmony patch that raises an event remains a Patch by primary mechanism.
_Avoid_: event-only handler, `HarmonyPatches/` as a universal requirement

**Events directory**:
The `Events/` category for event definitions, handlers, and subscription orchestration; Harmony bridges belong in `Patches/`.
_Avoid_: Harmony Patch file

**Commands directory**:
The `Commands/` category for Mod console command classes and their command-specific behavior.
_Avoid_: general-purpose service code

## Test lifecycle

**Test session**:
A single build-or-select, deploy, launch, evidence, stop, and cleanup lifecycle. A session has an identifier and temporary state.
_Avoid_: test run (when referring to persistent lifecycle state)

**Archived session**:
A completed or superseded session retained temporarily so that rollback can proceed in newest-first order.
_Avoid_: old run, stale session

**Safe clean**:
The default rollback operation. It restores files that were overwritten by the session and leaves files newly created by the session unless the user explicitly approves their removal.
_Avoid_: purge, wipe, full cleanup

**New deployment file**:
A target file that did not exist before the session deployed the package. Safe clean leaves this file by default.
_Avoid_: temporary file

**Manual verification**:
The player-operated part of testing, where the user performs game actions and describes the observed behavior in natural language. It is not an automated CLI result.
_Avoid_: automated gameplay test, pass status

**Session data**:
The per-Test-session temporary directory under the system temporary state root that contains the session manifest, rollback records, and any Test log snapshot.
_Avoid_: caller repository, game profile, live log directory

**Current log**:
The profile-local BepInEx log or configured Unity log that may still be written or overwritten by a later game launch.
_Avoid_: Test log snapshot, bounded evidence report

**Test log snapshot**:
The complete byte-preserving BepInEx and Unity log copies captured after the user confirms the Test session is complete. If the game remains running because stop was not approved or failed, the snapshot preserves the current content and records that capture condition; later analysis of that completed session uses these copies as evidence.
_Avoid_: current log, startup evidence report, bounded evidence

**Real-profile test**:
A verification path that requires a real, disposable, or mirror Modding profile and the game process; it may include **Manual verification** after startup evidence is collected.
_Avoid_: treating `mod_loaded` or startup logs as proof of gameplay behavior

**Automated xUnit test**:
A deterministic test executed by a .NET xUnit runner without starting the game, using a Modding profile, or requiring player actions; test doubles are allowed when they preserve that boundary.
_Avoid_: real-profile verification, gameplay proof

**Automated test project**:
The caller Mod repository's sibling `<ModRepoName>.Tests` project that contains Automated xUnit tests and references the main Mod project.
_Avoid_: the real-game Test Mod, the Skill repository's own Python fixture tests

**Test Mod**:
A separate Mod-owned build and package used to exercise behavior inside the real game during a Real-profile test; it is distinct from the Automated test project.
_Avoid_: xUnit test assembly, production Mod project

## Harmony vocabulary

**Patch file**:
A source file that groups related Harmony Patch classes.
_Avoid_: Patch class

**Patch class**:
A class that declares a Harmony target and provides one or more patch methods for a coherent behavior.
_Avoid_: patch file, general utility class

**Framework-managed patch discovery**:
The discovery and application of Mod-owned Harmony Patch classes performed by ModdingAPI during the Mod startup flow.
_Avoid_: Mod-owned `PatchAll`, manual assembly scan

**Manual patching**:
An explicit Harmony operation initiated by Mod code for a selected target rather than the normal framework-managed discovery flow.
_Avoid_: automatic patch discovery, `PatchAll` ownership

## Evidence

**Launched**:
The selected game process started and remained alive during the startup grace period.
_Avoid_: game passed

**Ready**:
The current game startup produced the BepInEx chainloader completion evidence.
_Avoid_: mod passed

**Mod loaded**:
The current startup log contains evidence that the target mod was loaded. This is stronger than the generic ready state.
_Avoid_: gameplay verified

**Unity log directory**:
The configured directory that contains the Unity player log for the selected game profile and platform.
_Avoid_: Unity log path (when the stored value is a directory)

**Session baseline**:
Structured log evidence that existed before the current Test session started; it does not mean that the evidence is harmless.
_Avoid_: known warning, suppressed log, baseline fingerprint

**Diagnostic ownership**:
The evidence-based attribution of a log record to the target Mod, the framework, the session baseline, or an unknown source.
_Avoid_: error blame, warning suppression

## Lifecycle vocabulary

**`BlasMod` lifecycle**:
The current ModdingAPI callback vocabulary for Mod startup, service registration, frames, levels, game sessions, and shutdown.
_Avoid_: Unity lifecycle, legacy `Mod` lifecycle

## Skill-document compression

**Live skill document**:
A Markdown document under the repository's `skills` tree that is part of an installed Skill and can be reviewed for compression.
_Avoid_: source code, caller document

**Candidate document**:
A compressed Markdown document produced for review that has not replaced its live skill document.
_Avoid_: final document, compressed source

**Compression run**:
A single identified lifecycle that discovers live skill documents, produces candidates, records review evidence, and may apply approved candidates.
_Avoid_: Test session, test run

**Protected content**:
Document content whose exact text, structure, or token identity must survive compression so that Skill behavior and operational guidance remain trustworthy.
_Avoid_: immutable prose
