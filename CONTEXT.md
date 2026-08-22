# Blasphemous Mod Test Context

This context defines the language for building, deploying, launching, and manually verifying a Blasphemous mod. It separates a build package from the modding profile and separates automated evidence from player-observed game behavior.

## Package and Profile

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

## Test Lifecycle

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
