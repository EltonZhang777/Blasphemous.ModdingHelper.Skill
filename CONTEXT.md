# Blasphemous Modding Helper Context

This context defines the vocabulary used by the skill when it generates or changes Blasphemous Mod code.

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

## Lifecycle vocabulary

**`BlasMod` lifecycle**:
The current ModdingAPI callback vocabulary for Mod startup, service registration, frames, levels, game sessions, and shutdown.
_Avoid_: Unity lifecycle, legacy `Mod` lifecycle
