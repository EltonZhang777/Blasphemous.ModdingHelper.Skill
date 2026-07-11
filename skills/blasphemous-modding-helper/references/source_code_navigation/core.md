# Core

Core navigation of the Blasphemous framework — infrastructure for all Managers, core systems, attribute system, audio, dialog, map, DLC, Boss Rush, achievements, etc.

> **Key Entry Points for Mod Development:**
> - `Core` is a global singleton, accessed via `Core.Instance`. Inherits from `Singleton<Core>`.
> - `Core.Logic` → `LogicManager`, `Core.Logic.Penitent` is the player instance (Penitent).
> - `Core.Events` → `EventManager`, manages the global Flag / Event system.
> - `Core.Input` → `InputManager`, manages player input (Rewired wrapper).

---

## Managers

The core Manager layer in the Framework, located at `Framework/Managers/`. All Managers inherit from `GameSystem` and are created and managed uniformly by `Core`.

> `Core` creates all Managers in `PreInit()` and exposes them as static properties, accessed via `Core.XXX`.

### Core Managers (Most Important)

- **Core.cs** - Global framework entry point. Inherits `Singleton<Core>`, initializes all `GameSystem` subsystems in `Awake`. Exposes all Managers as static properties (e.g., `Core.Logic`, `Core.Input`, `Core.Events`, etc.). Defines common delegate types (`SimpleEvent`, `EntityEvent`, etc.).
- **LogicManager.cs** - Game logic core. Manages the `LogicStates` state machine (Playing/Pause/Unresponsive, etc.), holds the `Penitent` player instance, `EnemySpawner`, `BreakableManager`, `PenitentSpawner`, `CameraShakeManager`, `ExecutionController`. Provides `SetState()`, `LoadMenuScene()`, `PauseGame()`/`ResumeGame()`.
- **EventManager.cs** - Event and Flag system. `LaunchEvent(id, parameter)` triggers events, `SetFlag(id, bool)` / `GetFlag(id)` manages persistent Flags. Implements `PersistentInterface` for save support. Manages Miriam side quest progress.
- **InputManager.cs** - Input management (based on Rewired). Supports keyboard/controller switching, `SetBlocker(name, blocking)` controls input blocking, `ActiveControllerType` gets the current input device type, `ApplyRumble()` controls controller vibration.
- **LevelManager.cs** - Level loading management. `ChangeLevel(levelName)` loads a level, `currentLevel` is the current level, `lastLevel` is the previous level. Manages the level loading lifecycle (`OnBeforeLevelLoad` → `OnLevelPreLoaded` → `OnLevelLoaded`). Manages safe respawn positions.

### Persistence & Save System

- **PersistentManager.cs** - Save system core. Manages the `SnapShot` snapshot system, supports 3 save slots. `SaveGame(slot)` / `LoadGame(slot)` for saving/loading, `ResetAll()` resets all data. `GetSlotData(slot)` gets save summary. Implements save backup/restore mechanism. Calculates game completion percentage.
- **PersistentManager.PersistentData** - Persistent data base class (abstract class).
- **PersistentManager.SnapShot** - Save snapshot, contains `commonElements` (cross-scene) and `sceneElements` (scene-specific).
- **PersistentManager.PublicSlotData** - Public slot data (for UI display).

### Inventory & Skills

- **InventoryManager.cs** - Inventory system core. Manages items: `Relic` (relic, 3 slots), `RosaryBead` (rosary bead, 8 slots), `Prayer` (prayer, 1 slot), `Sword` (sword heart, 1 slot), `QuestItem` (quest item), `CollectibleItem` (collectible), Boss Key. Provides `AddBaseObject()` / `
