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

**Modding profile**:
A game installation or mirror prepared for mod development, identified by its game launcher, Modding directory, and BepInEx installation.
_Avoid_: Steam install, game folder (when the modded profile is meant)

**Modding root**:
The Modding directory inside the selected modding profile. Package-relative files are deployed under this directory.
_Avoid_: mod folder (when the target must be precise)

**Plugin root**:
The plugins directory inside the modding root. A package's plugin files are mapped here without changing their package-relative names.
_Avoid_: DLL folder

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

## Lifecycle vocabulary

**`BlasMod` lifecycle**:
The current ModdingAPI callback vocabulary for Mod startup, service registration, frames, levels, game sessions, and shutdown.
_Avoid_: Unity lifecycle, legacy `Mod` lifecycle
