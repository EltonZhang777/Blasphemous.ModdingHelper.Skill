# Blasphemous Source Code Navigation Guide

Blasphemous source navigation. Paths relative to `Assembly-CSharp/`.

---

## Source Code Structure Overview

| Top-level Directory | Description |
|---------|------|
| `Framework/` | Core Framework, Managers, Attributes, Inventory, Maps, DLC |
| `Gameplay/` | Gameplay: Bosses, Enemies, Player, UI, Animation |
| `Tools/` | Tools/Utilities: Level, PlayMaker, Audio, NPC, Items |
| `Extras/` | Epic Online Services (EOS) Integrations |
| `I2/` | I2 Localization Framework |
| `VisualEffects/` | Screen color palette |
| `Effects/` | Blood particle fix tool |
| `HutongGames/` | PlayMaker Custom Actions |
| `TPO_FOLLOWER_PROTOTYPE/` | TPO Follower Prototype |
| Root `.cs` files | Miscellaneous tools, traps, effects, UI components, etc. |
| Other supporting roots (`LevelEditor/`, `Platforms/`, `Properties/`, `PygmyMonkey/`, `RewiredConsts/`, `Sauce3D/`) | Smaller source areas; search these paths directly when a requested type does not fit a domain route. |

---

## Navigation Routes

| Request signal / condition | Route destination | Boundary / next action |
|--------------------------|--------------------|------------------------|
| **Core.** Core Framework: Managers, Attributes, Audio, Dialog, Map, Penitences, BossRush, DLC, Pooling, Util, Achievements. Story Events (`EventManager`, `DialogManager`) — `Framework/Managers/`; Save System (`PersistentManager`) — `Framework/Managers/`; Core Framework (Attributes, Audio, Map, DLC) — `Framework/`, `Framework/FrameworkCore/`. | [core.md](core.md) | Agent MUST inspect the matching manager or framework class within the selected `Assembly-CSharp/` tree and verify its path before citing or tracing dependents. |
| **Player.** Player Penitent: Abilities, Attacks, Movement, Input, Animation, Prayers, State Machine. Player Actions (Penitent, Abilities, Input) — `Gameplay/GameControllers/Penitent/`. | [player.md](player.md) | Agent MUST inspect the relevant Penitent behavior within the selected `Assembly-CSharp/` tree and verify the class and file path before citing it. |
| **Enemy.** Enemy System: All enemy types, AI Framework, Entity Base Classes. Enemy AI (`EnemyBehaviour`, `EnemyAI`) — `Gameplay/GameControllers/Enemies/`; Entity Base Classes (`Entity`, `Enemy`, `Hit`, `Attack`) — `Gameplay/GameControllers/Entities/`. | [enemy.md](enemy.md) | Agent MUST identify whether the question concerns enemy AI or shared entity bases within the selected `Assembly-CSharp/` tree, then verify the class hierarchy and file path. |
| **Bosses.** Boss System: All Boss types, BossFightManager, Common Attacks. Boss Combat (`BossFightManager`, `BossBehaviour`) — `Gameplay/GameControllers/Bosses/`. | [bosses.md](bosses.md) | Agent MUST inspect the boss or shared combat behavior within the selected `Assembly-CSharp/` tree and verify its file path before tracing the fight flow. |
| **UI.** UI System: UIController, Widgets, MenuLogic, HUD, Console. UI Screens (`UIController`, Widgets, MenuLogic) — `Gameplay/UI/`; Console Commands (`Console/`) — `Gameplay/UI/Console/`. | [ui.md](ui.md) | Agent MUST choose the screen/widget or console path that matches the request within the selected `Assembly-CSharp/` tree and verify the cited UI class there. |
| **Items.** Item/Equipment System: Inventory item types, Effect System, Achievements. Item Effects (`ObjectEffect`, `RelicEffect`, `RosaryBead`) — `Framework/Inventory/`, `Tools/Items/`. | [items.md](items.md) | Agent MUST inspect the item or effect implementation within the selected `Assembly-CSharp/` tree and verify its path before following its inventory or achievement behavior. |
| **Level.** Level/Environment: Actionables, Interactables, Layout, Teleport. Level Mechanics (Actionables, Interactables, Teleport) — `Tools/Level/`. | [level.md](level.md) | Agent MUST inspect the matching level mechanic within the selected `Assembly-CSharp/` tree and verify its file path before tracing scene interactions. |
| **Tools.** Tool Set: PlayMaker Actions/Conditions/Events, Audio, Data Containers, NPC. PlayMaker Scripts (Playmaker2/Action, Condition, Events) — `Tools/Playmaker2/`. | [tools.md](tools.md) | Agent MUST use the matching tool family as the search entry within the selected `Assembly-CSharp/` tree and verify each cited class or path there. |
| **Localization.** Localization System: I2.Loc, Blasphemous's own LocalizationManager. Localization / Translation — `I2/`, `Framework/Managers/LocalizationManager.cs`. | [localization.md](localization.md) | Agent MUST inspect I2 localization or the game LocalizationManager as indicated within the selected `Assembly-CSharp/` tree and verify the source path before citing strings or behavior. |
| **Lifecycle.** Cross-domain ownership and runtime flow: framework setup, scene transitions, subsystem or actor lifecycle, shared events, and teardown. | [core.md](core.md), then the relevant domain guide | Agent MUST start at `Framework/Managers/Core.cs`, `LogicManager.cs`, or `LevelManager.cs` for system or scene flow; otherwise start at the feature's domain route and follow its shared base and lifecycle/event links. |

---

This guide indexes decompiled game source under `Assembly-CSharp/`. For Mod-owned changes, [Project architecture guidelines](../sub-skills/project-architecture-guidelines.md) own project structure, [Harmony patching standards](../coding-standards/coding-standards-harmony-patching.md) own patches, and the [Mod-test entry](../sub-skills/blasphemous-modding-test.md) owns verification.

## Quick Access for Mod Development

| Entry Point | Description |
|------|------|
| `Core.Instance` | Global framework singleton |
| `Core.Logic` | LogicManager, game logic core |
| `Core.Logic.Penitent` | Player Penitent instance |
| `Core.Events` | EventManager, Flag/Event system |
| `Core.Input` | InputManager, input management |
| `Core.LevelManager` | Level loading |
| `Core.Persistence` | Save system |
| `Core.InventoryManager` | Inventory system |
| `Core.SkillManager` | Skill system |
| `Core.AudioManager` | Audio management |
| `Core.DialogManager` | Dialog system |
| `Core.ColorPaletteManager` | Color palette management |
| `UIController.instance` | UI system singleton |

---

## Common Namespaces

| Namespace | Description |
|---------|------|
| `Framework.Managers` | All core Manager classes |
| `Framework.FrameworkCore` | Attribute system, entity states, abilities |
| `Framework.Inventory` | Item/Equipment/Effect system |
| `Gameplay.GameControllers.Penitent` | All Player-related |
| `Gameplay.GameControllers.Enemies` | All Enemy-related |
| `Gameplay.GameControllers.Bosses` | All Boss-related |
| `Gameplay.GameControllers.Entities` | Entity Base Classes (Entity, Enemy, Hit, Attack) |
| `Gameplay.GameControllers.Camera` | Camera System |
| `Gameplay.UI` | All UI-related |
| `I2.Loc` | I2 Localization Framework |
| `Tools.Playmaker2` | PlayMaker Custom Actions |
