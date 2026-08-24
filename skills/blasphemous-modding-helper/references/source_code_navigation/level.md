# Level / Environment / Interactables

Level-related systems: actionables, interactables, layout building, effects, and utilities in Blasphemous source code.

> Base path: `Tools/Level/`

## Core Design Patterns

1. **IActionable Chaining** — `TriggerReceiver`, `BreakableInteractor`, `SlashReceiver`, etc. cascade activation of other objects via `IActionable[]` arrays.
2. **PersistentObject Persistence** — Most interactive objects inherit from `PersistentObject`, saving state via `BasicPersistence` or custom `PersistenceData`.
3. **Interactable Lifecycle** — Virtual methods `OnUse()` / `OnAwake()` / `OnStart()` / `OnUpdate()` / `PlayerReposition()` form extensible interactive base class.
4. **IDamageable Direction Lock** — `BreakableWall` / `PersistentBreakableObject` / `SlashReceiver` use `DAMAGEABLE_DIRECTION_LOCK` enum to restrict hit direction.
5. **Material Tag Audio** — `ElusivePlatform` etc. use GameObject tag (e.g., `Material:Stone`) to determine audio prefix.
6. **DOTween Animation** — Most transitions (doors, platforms, hidden areas) use DOTween for smooth animation.
7. **PoolManager Object Pooling** — Frequently-created objects like `ShockwaveArea` are reused via PoolManager.

---

## Actionables

`Tools/Level/Actionables/` — Objects implementing `IActionable` interface, activated via lever, switch, trigger, or direct interaction.

### IActionable (`Tools/Level/IActionable.cs`)
Interface with `Use()` and `Locked { get; set; }`. Core contract for all actionable objects.

### ActionableSwitch (`Actionables/ActionableSwitch.cs`)
Simple on/off switch. `ChangeState(bool turnOn)` toggles `isOn`, fires `OnSwitchUsed` event.

### ActionableLadder (`Actionables/ActionableLadder.cs`)
Extendable ladder. `PersistentObject` + `IActionable`. Uses `TileableBeamLauncher` for growth animation. Supports `startOpen`, `persistState`, `maxRange`, open/close FMOD sounds.

### ActionableForce (`Actionables/ActionableForce.cs`)
Applies physics force to Rigidbody2D. `fromPenitent` flag computes direction away from player. `HeavyUse()` doubles force multiplier.

### AshPlatform (`Actionables/ActionablePlatform` -> `Actionables/AshPlatform.cs`)
Temporary platform: `Show()` / `Hide(delay)`. Uses DOTween for transition, `MasterShaderEffects` for warning colorize before deactivation. `IActionable`, not `PersistentObject`.

### BasicTrap (`Actionables/BasicTrap.cs`)
Core trap system. `MonoBehaviour` + `IActionable`. States: Idle / Moving. Features: looping, activation delay, reactivation time, ANTICIPATION animation support, damage-on-contact via sensors. Configurable damage type/element, audio events.

### BreakableDamageArea (`Actionables/BreakableDamageArea.cs`)
Extends `DamageArea`. Adds `grantsFervour` flag — when true, hitting breakable in this area grants fervour.

### BreakableInteractor (`Actionables/BreakableInteractor.cs`)
Extends `Interactable`. Requires `BreakableObject` component. On break, activates linked `IActionable[] InteractionTargets` after `InteractionTimeout` delay.

### BreakableObject (`Actionables/BreakableObject.cs`)
Destructible object. `PersistentObject` + `IActionable` + `IDamageable`. Persisted via `BreakableManager`. On break: plays animation, disables damage collider, triggers `OnBreak` event. Restored on PrieDieu use. Supports soft/hard disable modes.

### BreakableWall (`Actionables/BreakableWall.cs`)
Destructible wall barrier. `PersistentObject` + `IActionable` + `IDamageable`. Directional break (BOTH/LEFT/RIGHT). Health system, `SecretReveal`, `OnDestroy` targets (IActionable chain). Integrates with `LayoutElement` / `Category.Layout` for visual mode.

### DestroyableBridge (`Actionables/DestroyableBridge.cs`)
Bridge that moves to `Destination` transform on Use(). DOTween interpolation with `translationCurve` / `rotationCurve`. FMOD audio. Persistent (alreadyUsed).

### ElusivePlatform (`Actionables/ElusivePlatform.cs`)
Platform that disappears when entity stands on it, reappears after `RecoverTime`. Supports decorative (animator) and layout-only modes. Material-based audio (stone/wood/glass/demake). Implements `INoSafePosition`.

### Fader (`Actionables/Fader.cs`)
Simple `SpriteRenderer` fade-out via `DOFade`. `IActionable`. Configurable `time`.

### FaithPlatform (`Actionables/FaithPlatform.cs`)
Revealable platforms triggered by flag `REVEAL_FAITH_PLATFORMS`. First platform in chain is entry point. DOTween color transition, FMOD sounds. `INoSafePosition`.

### GameobjectActivator (`Actionables/GameobjectActivator.cs`)
Toggles `GameObject.SetActive()` on target array. `PersistentObject` + `IActionable`. Supports `persistState`.

### Gate (`Actionables/Gate.cs`)
Openable gate with animator. `PersistentObject` + `IActionable`. `startOpen`, `persistState`, open/close FMOD sounds. Insta-action support.

### GlobalTrapTriggerer (`Actionables/GlobalTrapTriggerer.cs`)
Triggers all scene traps via `TriggerTrapManager.Trigger(string id)`. Default trigger ID: `"SHOCK"`.

### HiddenArea (`Actionables/HiddenArea.cs`)
Secret wall that fades out when player enters trigger. DOTween alpha fade on all SpriteRenderers, disables Collider2Ds. Fires `SECRET_DISCOVERED` metric. `OnUse` static event.

### ImpacteableObject (`Actionables/ImpacteableObject.cs`)
Non-breakable object that plays FMOD sound on hit. `IDamageable` only. Has bleed/spark impact flags.

### PersistentBreakableObject (`Actionables/PersistentBreakableObject.cs`)
Advanced breakable with health, multi-hit support, damage events (PlayMaker FSM broadcast), directional break, animator HEALTH float. `OnDestroy` IActionable chain. Similar to BreakableWall but richer — damage events at specific health thresholds.

### ShockwaveArea (`Actionables/ShockwaveArea.cs`)
Extends `Weapon`. Duration-based area attack with camera shockwave effect. Pooled (`PoolManager`). FMOD audio, animator ACTIVE trigger.

### SimpleDamageArea (`Actionables/SimpleDamageArea.cs`)
Extends `Weapon`. Persistent damage area with tick-rate control. Configurable damage type/element/force. Creates dummy `AreaAttackDummyEntity` for attack attribution. Horizontal damage mode.

### SlashReceiver (`Actionables/SlashReceiver.cs`)
Receives player slash hits, activates linked `OnHitUse` IActionable targets. Directional lock (BOTH/LEFT/RIGHT). Special: `ActionableForce` targets get `HeavyUse()` on heavy damage.

### TileableGeo (`Actionables/TileableGeo.cs`)
Tile-based geometry that grows/shrinks. Supports 4 directions, relic-based reveal (RE10), body-part prefab spawning with delayed animation. FMOD grow roots audio. States: HIDDEN / SHOWING / SHOWN / HIDING.

### TriggerBasedTrap (`Actionables/TriggerBasedTrap.cs`)
Trigger-ID-based trap. Spawns `ShockwaveArea` via PoolManager. States: IDLE / CHARGING / ACTIVE. Player damage triggers CHARGING → auto-activate. Cooldown system. `OnUsedEvent` delegate.

### TriggerReceiver (`Actionables/TriggerReceiver.cs`)
Receives `TrapTriggererArea` trigger by ID, activates linked IActionable targets. `PersistentObject`. DOTween punch scale on use. One-time use (`alreadyUsed`).

### TriggerTrapManager (`Actionables/TriggerTrapManager.cs`)
Manages all `TriggerBasedTrap` instances in scene. `Trigger(string id)` activates all matching traps. `LinkToSceneTraps()` auto-discovers traps. Configurable `firstTrapLapse` / `loopTrapLapse`.

### TriggerTrapManagerAutogenerator (`Actionables/TriggerTrapManagerAutogenerator.cs`)
`ExecuteInEditMode`. Auto-creates `TriggerTrapManager` GameObject if none exists. One-shot via `executedFlag`.

---

## Interactables

`Tools/Level/Interactables/` — Objects extending `Interactable` base class, player-interactive via input button.

### Interactable (`Tools/Level/Interactable.cs`)
Base class for all interactable objects. Extends `PersistentObject`, implements `IActionable`. Key features:
- Sensor-based player detection (`CollisionSensor[]`)
- `RepositionBeforeInteract` with Waypoint
- `requiredItem` — inventory object check (locks if not equipped)
- `Consumed` flag with persistence
- `BeingUsed` / `PlayerInRange` / `InteractionTriggered` state
- FMOD-style animation event hooks (`INTERACTION_START` / `INTERACTION_END`)
- Static events: `SConsumed`, `Created`, `SPenitentEnter`, `SPenitentExit`, `SLocked`, `SUnlocked`, `SInteractionStarted`, `SInteractionEnded`
- Virtual lifecycle hooks: `OnUse()`, `OnAwake()`, `OnStart()`, `OnUpdate()`, `OnPlayerReady()`, `PlayerReposition()`, `TriggerEnter()`, `TriggerExit()`

### Altar (`Interactables/Altar.cs`)
Confessor altar interaction. Extends `Interactable`. 7 visual levels based on `Core.Alms.GetAltarLevel()`. Player kneels → offers alms menu / confessor guilt purge. DOTween-driven reposition. FMOD knee sounds. Fires "ALTAR_ACTIVATED" event.

### Chest (`Interactables/Chest.cs`)
Loot chest. Extends `Interactable`. `ChestMode` enum (likely `Interactive`/`Automatic`). On use: hides player, plays activation sound, triggers interactor animation. `Consumed` persisted.

### ChestMode (`Interactables/ChestMode.cs`)
Enum defining chest activation mode (Interactable — player presses button; alternative mode for auto-open).

### DemakeAltar (`Interactables/DemakeAltar.cs`)
8-bit demake version of Altar. Likely simplified interaction for retro mini-game.

### Door (`Interactables/Door.cs`)
Scene transition door. Extends `Interactable`. Features:
- Required quest item check with popup message
- `spawnPoint` / `exitOrientation` for exit positioning
- `ExitFromThisDoor()` / `ExitDoorSafe()` coroutine
- Disables/enables player physics during transition
- Static events: `OnDoorEnter`, `OnDoorExit`
- ProCamera2D integration for camera transitions

### Execution (`Interactables/Execution.cs`)
Execution move system for enemies. Extends `Interactable`, implements `IDamageable`. Contains:
- `ExecutedEntity` (Enemy) and `Penitent` references
- `RootMotionDriver` for animation-driven movement
- `EnemyDamageArea` for execution hitbox
- `GhostTrail` / camera zoom for visual flair
- DOTween-based camera effects

### ExecutionAnimationEvents (`Interactables/ExecutionAnimationEvents.cs`)
Animation event receiver for execution cutscenes. Handles animation-triggered callbacks.

### ExecutionAwareness (`Interactables/ExecutionAwareness.cs`)
Enemy component for execution-eligible state detection/marking.

### FakeExecution (`Interactables/FakeExecution.cs`)
Non-lethal execution variant (likely for tutorial or specific encounters).

### GuiltDropCollectibleItem (`Interactables/GuiltDropCollectibleItem.cs`)
Collectible guilt fragment dropped on death. Player picks up to recover guilt.

### InteractableGuiltDrop (`Interactables/InteractableGuiltDrop.cs`)
Interactable wrapper for guilt drop pickup behavior.

### Lever (`Interactables/Lever.cs`)
Toggleable lever. Extends `Interactable`. Two-position (UP/DOWN). Buttons: `SetLeverUp()`, `SetLeverUpInstantly()`, `SetLeverDown()`. DOTween punch on interaction. Plays activation sound. Supports instant animation mode.

### LeverAction (`Interactables/LeverAction.cs`)
Action definition linked to lever state changes — bridges lever to IActionable targets.

### LeverMode (`Interactables/LeverMode.cs`)
Enum defining lever behavior mode (e.g., toggle vs one-shot).

### MiriamExit (`Interactables/MiriamExit.cs`)
Miriam (Bloodstained crossover) exit transition handler.

### MiriamPortal (`Interactables/MiriamPortal.cs`)
Miriam portal — entry point for Bloodstained crossover event.

### MiriamStart (`Interactables/MiriamStart.cs`)
Miriam appearance trigger — starts crossover sequence.

### PrieDieu (`Interactables/PrieDieu.cs`)
Save point / fast-travel shrine. Extends `Interactable`. 3 visual levels via `Core.Alms.GetPrieDieuLevel()`. Player kneels → kneel menu (save, teleport, etc). Lights up on first use (`Ligthed`). Fires `OnUsePrieDieu` event (triggers breakable restoration worldwide).

### ActivateIfDLCInstalled (`Interactables/ActivateIfDLCInstalled.cs`)
Conditionally enables/disables GameObject based on DLC installation status.

---

## Layout (Level Layout)

`Tools/Level/Layout/` — Level construction, category system, spawn points.

### Category (`Layout/Category.cs`)
Enum: `Layout`, `Audio`, `Decoration`, `Gameplay`. Used by `LayoutElement` and `LevelBuilder` to categorize level geometry.

### DebugSpawn (`Layout/DebugSpawn.cs`)
Debug spawn point configuration for testing.

### EnemySpawnPoint (`Layout/EnemySpawnPoint.cs`)
Defines enemy spawn position and parameters within level layout.

### LadderLayout (`Layout/LadderLayout.cs`)
Layout-specific ladder configuration (separate from ActionableLadder).

### LayoutElement (`Layout/LayoutElement.cs`)
Core element for level geometry. Each room piece has `LayoutElement` with `Category` and `SpriteRenderer` reference. Used by `BreakableWall`, `PersistentBreakableObject`, `ElusivePlatform` for layout mode toggling.

### LevelBuilder (`Layout/LevelBuilder.cs`)
`ExecuteInEditMode`. `Category Mode` property — switches level building modes. Shortcut: Ctrl+E.

### LevelInitializer (`Layout/LevelInitializer.cs`)
`[DefaultExecutionOrder(-1)]`. Scene-level initialization. Configures:
- Guilt system mode (Default / OverridePosition)
- Level sleep state (`IsSleeping`)
- Player spawn, enemy balance, blob shadow, color effects
- Level debug flag

### NonExecutionPlatform (`Layout/NonExecutionPlatform.cs`)
Platform marker preventing execution moves on certain surfaces.

### PopPenitentFromGeo (`Layout/PopPenitentFromGeo.cs`)
Handles penitent being pushed out of geometry when stuck.

---

## Effects (Visual Effects)

`Tools/Level/Effects/` — Level-wide color grading and visual effects.

### LevelColorEffectData (`Effects/LevelColorEffectData.cs`)
Struct: `colorizeColor`, `colorizeAmount`, `colorizeMultColor`. Defines color grading for level.

### ScriptableLevelEffects (`Effects/ScriptableLevelEffects.cs`)
`[CreateAssetMenu]` ScriptableObject. `Dictionary<LEVEL_COLOR_CONFIGS, LevelColorEffectData>`. Database mapping level enum to color effect data.

### LEVEL_COLOR_CONFIGS (`Effects/LEVEL_COLOR_CONFIGS.cs`)
Enum defining all level color configurations (used as dictionary key in ScriptableLevelEffects).

---

## Utils (Utility Classes)

`Tools/Level/Utils/` — Spawn configurators for level entities.

### CherubCaptorSpawnConfigurator (`Utils/CherubCaptorSpawnConfigurator.cs`)
Configures cherub captor spawn points within levels.

### EnemySpawnConfigurator (`Utils/EnemySpawnConfigurator.cs`)
Configures enemy spawn behavior and parameters.

### FlyingPatrollingEnemySpawnConfigurator (`Utils/FlyingPatrollingEnemySpawnConfigurator.cs`)
Configures flying patrolling enemy spawn points with patrol path data.

---

## Other

### Region (`Tools/Level/Region.cs`)
`[RequireComponent(typeof(Collider2D))]`. Trigger-based region boundary. Static events: `OnRegionEnter`, `OnRegionExit`. Tracks `EntitiesInside` count.

### Teleport (`Tools/Level/Teleport.cs`)
Teleport destination marker. Extends `PersistentObject`. Fields: `telportName`, `spawnOrientation`, `showOnMap`.

### LevelSleepTime (`Tools/Level/LevelSleepTime.cs`)
`[Serializable]` class implementing `PersistentInterface`. Stores three float values (`Normal`, `Heavy`, `Critical`) and maps `DamageType` → sleep time via `GetHitSleepTime(Hit hit)`.

---
