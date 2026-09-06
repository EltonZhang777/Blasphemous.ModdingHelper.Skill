# Tools / PlayMaker / Miscellaneous

Source code navigation for custom tools, PlayMaker FSM Actions/Conditions/Events, data containers, NPCs, level tools, and other miscellaneous items.

## Core Design Patterns

1. PlayMaker triad: Action (execute) / Condition (check) / Event (signal), named by verb prefix
2. Deprecated components centralized under "PlayMaker Deprecated" — Mod code MUST NOT use these components in new code
3. Audio tools layered: Emitter (play) → Modifier (spatial / temporal / parameter)

---

## PlayMaker Actions

### Action/

- `ActionableActivation.cs` - Forcefully activate/deactivate interactable object (Actionable)
- `AddAchievementProgress.cs` - Add achievement progress
- `AddCorpseAchievementProgressAC14.cs` - AC14 corpse achievement progress addition
- `AmbientSet.cs` - Set ambient audio parameters
- `AreaEmitterOneShot.cs` - Area audio one-shot trigger
- `ArrayFindGameObjectsByName.cs` - Find GameObject array by name
- `BeadUpgrade.cs` - Bead slot upgrade
- `BehaviourStart.cs` - Start Behaviour
- `BehaviourStop.cs` - Stop Behaviour
- `BossKeyCheck.cs` - Boss key check
- `BossKeySet.cs` - Set Boss key state
- `CameraFade.cs` - Camera fade in/out
- `CameraFollowPlayer.cs` - Camera follows player
- `CameraModeFree.cs` - Camera free mode
- `CameraModeNormal.cs` - Camera normal mode
- `CheckAchievement.cs` - Check if achievement is unlocked
- `CheckAchievementProgress.cs` - Check achievement progress
- `CheckFlagsToGrantAchievementAC36.cs` - AC36 achievement flag check
- `CheckGameModeActive.cs` - Check if game mode is active
- `CheckLastDLC.cs` - Check last DLC
- `CheckPurchasedSkills.cs` - Check purchased skills
- `CheckRescuedCherubs.cs` - Check rescued cherubs count
- `CountRetrievedCollectibles.cs` - Count retrieved collectibles
- `CutscenePlay.cs` - Play cutscene
- `CutsceneStop.cs` - Stop cutscene
- `DialogStart.cs` - Start dialog
- `DisableInventoryAndUnequip.cs` - Disable inventory and unequip items
- `DisablePenitentBloodPenance.cs` - Disable blood penance
- `DisablePenitentHealing.cs` - Disable player healing
- `DisablePenitentPrayers.cs` - Disable player prayers
- `DisableStuntFall.cs` - Disable stun fall
- `DisplayZoneTitle.cs` - Display zone title
- `EasyFadeOutAndIn.cs` - Easy fade out and in
- `EnableUnlimitedFervour.cs` - Enable unlimited fervour
- `EndCinematicsInOtherScene.cs` - End cinematics in other scenes
- `EndDemakeRun.cs` - End Demake run
- `EntityDamage.cs` - Entity takes damage
- `EntityHeal.cs` - Entity heal
- `EntityKill.cs` - Entity killed
- `Fade.cs` - Fade
- `FervourAdd.cs` - Add fervour
- `FervourUpgrade.cs` - Fervour max upgrade
- `FlagModification.cs` - Modify flag
- `FlaskAdd.cs` - Add flask
- `FlaskHealthUpgrade.cs` - Flask health upgrade
- `FlaskRefill.cs` - Refill flasks
- `FlaskRemove.cs` - Remove flask
- `GetBeadSlots.cs` - Get bead slots count
- `GetFervour.cs` - Get current fervour
- `GetFervourMax.cs` - Get max fervour
- `GetFilledFlask.cs` - Get filled flask count
- `GetFlaskMax.cs` - Get flask max
- `GetGuilt.cs` - Get guilt
- `GetLife.cs` - Get current life
- `GetLifeMax.cs` - Get max life
- `GetMeaCulpa.cs` - Get Mea Culpa level
- `GetMiriamClosedPortals.cs` - Get Miriam closed portals count
- `GrantAchievement.cs` - Grant achievement
- `GuiltReset.cs` - Reset guilt
- `HideMiriamTimer.cs` - Hide Miriam timer
- `InputIconSetAction.cs` - Set input icon action
- `IsFervourMaxed.cs` - Is fervour maxed
- `IsItemEquipped.cs` - Is item equipped
- `IsSantosCutscenePlaying.cs` - Is Santos cutscene playing
- `ItemAddition.cs` - Add item
- `ItemAdditionMessage.cs` - Add item and show message
- `ItemEquip.cs` - Equip item
- `ItemSubstraction.cs` - Remove item
- `ItemSubstractionMessage.cs` - Remove item and show message
- `ItemUnequip.cs` - Unequip item
- `LifeAdd.cs` - Add life
- `LifeRefill.cs` - Full life refill
- `LifeUpgrade.cs` - Life max upgrade
- `MapChange.cs` - Change map
- `MapRevealSecret.cs` - Reveal map secret
- `MarkCourseAsUnlocked.cs` - Mark course as unlocked
- `MeaCulpaUpgrade.cs` - Mea Culpa upgrade
- `MiriamQuestStart.cs` - Start Miriam quest
- `PenitenceCheckCurrent.cs` - Check current penitence
- `PenitenceCompleteCurrent.cs` - Complete current penitence
- `PlayerTeleport.cs` - Player teleport
- `PlayerUseHealing.cs` - Player uses healing
- `PopUpDialog.cs` - Pop up dialog
- `Purge.cs` - Purge (clear guilt)
- `PurgeAdd.cs` - Add purge points
- `PurgeSet.cs` - Set purge points
- `ResetAllWaypointPlatforms.cs` - Reset all waypoint platforms
- `ResetHighWills.cs` - Reset High Wills
- `ResetRetrievedCollectibles.cs` - Reset retrieved collectibles
- `RespawnMiriam.cs` - Respawn Miriam
- `RumbleStart.cs` - Start rumble
- `RumbleStop.cs` - Stop rumble
- `SendMetric.cs` - Send metric
- `SequencePlay.cs` - Play sequence
- `SequenceStop.cs` - Stop sequence
- `SetPenitentInvincible.cs` - Set penitent invincible
- `SetSantosCutscenePlaying.cs` - Set Santos cutscene playing state
- `ShowCredits.cs` - Show credits
- `ShowFlasksUpgradePopup.cs` - Show flasks upgrade popup
- `ShowFullMessage.cs` - Show full message
- `ShowHowToPlayPopup.cs` - Show how-to-play popup
- `ShowMessage.cs` - Show message (tooltip above dialog box)
- `ShowMiriamTimer.cs` - Show Miriam timer
- `ShowPenitenceAbandonmentPopup.cs` - Show penitence abandonment popup
- `ShowPenitenceSelectionPopup.cs` - Show penitence selection popup
- `ShowQuotePopup.cs` - Show quote popup
- `ShowUI.cs` - Show specified UI
- `StartCinematicsInOtherScene.cs` - Start cinematics in other scenes
- `StartMiriamTimer.cs` - Start Miriam timer
- `StopCurrentMusic.cs` - Stop current music
- `StopMiriamTimer.cs` - Stop Miriam timer
- `StrengthUpgrade.cs` - Strength upgrade (attack power)
- `Teleport.cs` - Teleport
- `TeleportPenitentToSafePosition.cs` - Teleport penitent to safe position
- `TeleportSetActive.cs` - Activate/deactivate teleport point
- `TeleportToBossRushHub.cs` - Teleport to Boss Rush hub
- `TeleportToBossRushNextScene.cs` - Teleport to Boss Rush next scene
- `TeleportUI.cs` - Teleport UI control
- `ThunderScreenEffect.cs` - Thunder screen effect
- `UnlockSkillsMenu.cs` - Unlock skills menu
- `UnlockSkin.cs` - Unlock skin
- `WaitForCreditsEnd.cs` - Wait for credits to end
- `WaitForInput.cs` - Wait for player input
- `WaitForMiriamTimerToRunOut.cs` - Wait for Miriam timer to run out

### Actionn/

- `FadeToMainMenu.cs` - Fade to main menu

## PlayMaker Conditions

- `EntityIsPenitent.cs` - Whether entity is player (Penitent)
- `FlagExists.cs` - Whether flag exists
- `InteractableIsConsumed.cs` - Whether interactable is consumed
- `InteractableIsLocked.cs` - Whether interactable is locked
- `IsAltarTierGreaterOrEqual.cs` - Whether altar tier is >= specified value
- `IsDLCDownloaded.cs` - Whether DLC is downloaded
- `IsEntityDead.cs` - Whether entity is dead
- `IsSkinUnlock.cs` - Whether skin is unlocked
- `IsTipUnlocked.cs` - Whether tip is unlocked
- `ItemIsEquiped.cs` - Whether item is equipped
- `ItemIsOwned.cs` - Whether item is owned
- `NoItemEquiped.cs` - Whether no item is equipped
- `ObjectIsType.cs` - Whether object is of specified type
- `TeleportIsActive.cs` - Whether teleport point is active

## PlayMaker Events

- `ActionableSwitchOrFlagRaised.cs` - Switch activation or flag raised event
- `ActionableSwitchUsed.cs` - Switch used event
- `CinematicEnded.cs` - Cinematic ended event
- `CinematicStarted.cs` - Cinematic started event
- `DestructibleDead.cs` - Destructible destroyed event
- `EntityAttacked.cs` - Entity attacked event
- `EntityDead.cs` - Entity dead event
- `EntityStarted.cs` - Entity started event
- `FlagDropped.cs` - Flag dropped event
- `FlagRaised.cs` - Flag raised event
- `GameInitialized.cs` - Game initialized event
- `InteractableDeactivation.cs` - Interactable deactivation event
- `InteractableInteractionEnded.cs` - Interactable interaction ended event
- `InteractableInteractionStarted.cs` - Interactable interaction started event
- `InteractableLocked.cs` - Interactable locked event
- `InteractableUnlocked.cs` - Interactable unlocked event
- `RegionEnter.cs` - Region enter event
- `RegionExit.cs` - Region exit event

### PlayMaker Deprecated

- `ChangeCamera.cs` - Change camera (Deprecated)
- `CheckFlag.cs` - Check flag (Deprecated)
- `EventListener.cs` - Event listener (Deprecated)
- `InCinematicMode.cs` - In cinematic mode (Deprecated)
- `LaunchEvent.cs` - Launch event (Deprecated)
- `LevelInitialization.cs` - Level initialization (Deprecated)
- `SetCinematicMode.cs` - Set cinematic mode (Deprecated)
- `SetFlag.cs` - Set flag (Deprecated)
- `UnlockActionable.cs` - Unlock actionable (Deprecated)

## Audio Tools

- `AmbientMusic.cs` - Ambient music controller
- `AmbientMusicSettings.cs` - Ambient music configuration data
- `AreaEmitter.cs` - Area audio emitter
- `AreaModifier.cs` - Area audio modifier
- `AudioParam.cs` - Audio parameter definition
- `AudioParamInitialized.cs` - Audio parameter initializer
- `AudioParamName.cs` - Audio parameter name enum
- `AudioState.cs` - Audio state definition (Snapshot)
- `AudioTool.cs` - Audio utility methods
- `CreateFxOnEnable.cs` - Create FX on enable
- `DangerEmitter.cs` - Danger state audio emitter
- `GlobalEmitter.cs` - Global audio emitter
- `ParameterData.cs` - Audio parameter data container
- `PlaySoundFXOnStart.cs` - Play sound FX on start
- `SceneAudio.cs` - Scene audio manager
- `SceneAudioModifer.cs` - Scene audio modifier
- `ShotEmitter.cs` - One-shot audio emitter
- `SpatialModifier.cs` - Spatial audio modifier
- `TemporalModifier.cs` - Temporal audio modifier (pitch/speed)

## Data Containers

- `AlmsConfigData.cs` - Alms configuration data
- `CinematicType.cs` - Cinematic type definition
- `CutsceneData.cs` - Cutscene data container
- `EnemiesBalance.cs` - Enemy balance parameters
- `GuiltConfigData.cs` - Guilt configuration data
- `ImageList.cs` - Image list container
- `MapData.cs` - Map data
- `RumbleData.cs` - Rumble data
- `RummbleBlock.cs` - Rumble block
- `SharedCommand.cs` - Shared command definition
- `SubTitleBlock.cs` - Subtitle block

> Localization data containers (`LocalizationSpacingData.cs`, `TimeLocalization.cs`) are documented in [localization.md](localization.md).

## NPC

- `NPC.cs` - NPC base class, manages NPC dialog, appearance, and interaction logic

## Gameplay Utilities

- `BasicPersistence.cs` - Basic persistence (saves GameObject activation state across scenes)
- `ColliderUtil.cs` - Collider utility methods
- `CombatDummy.cs` - Combat dummy (for testing)

## Other / Miscellaneous

### Items

> Item effect scripts under `Tools/Items/` are documented in [items.md](items.md) (Special Item Effects section).

### Level

> Level scripts under `Tools/Level/` (Actionables, Interactables, Layout, Effects, Utils) are documented in [level.md](level.md).

### UI (UI Utilities)

- `InputEnableObjects.cs` - Input enable objects management
- `InputIcon.cs` - Input icon display
- `InputNotifier.cs` - Input notifier

### Util (Utility Functions)

- `AnimationRandomLoop.cs` - Animation random loop (random starting frame)
- `EditorTools.cs` - Editor tools
- `RandomFrame.cs` - Random frame setting

### Tools Root Directory

- `BundleLoader.cs` - AssetBundle loader
- `FileTools.cs` - File tools
- `MainMenuLoader.cs` - Main menu loader

### Playmaker2 Root Directory

- `InventoryBase.cs` - Inventory system base class
- `IsShowingInventory.cs` - Whether inventory is showing
- `ObjectCategory.cs` - Object category enum
- `PlaymakerCache.cs` - PlayMaker cache manager

### HutongGames/PlayMaker/Actions/ Custom Actions

- `FindGameObjectsResourcesWithNameContaining.cs` - Find GameObjects in Resources by name containing
- `GetParentMore.cs` - Enhanced get parent (supports multiple levels)
- `WaitForGameObject.cs` - Wait for specified GameObject to be ready
